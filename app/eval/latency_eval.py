"""Latency and cost measurement for the assessment pipeline.

Fills Table 4.10 and Figure 4.9, which the report has carried as
`[TBD-EXPERIMENT: eval_latency]` in seven places because no instrumentation
existed.

What is measured, and how honestly:

* **Per-stage latency** - every deterministic stage (crisis rule, lexicon,
  PhoBERT inference, retrieval, DASS-21/PSS-10 scoring) is timed directly over
  repeated runs on real dataset text. These need no network and no key, so they
  are measured exactly, not estimated.
* **Cold start** - the one-off cost of loading the PhoBERT classifier and the
  sentence-transformers embedder, timed with the module caches cleared. This is
  paid once per process, not once per request, and is reported separately so it
  is never averaged into a per-session number.
* **LLM latency and tokens** - measured only if `--llm-samples` is greater than
  zero, because each sample is a real billable request. Token counts come from
  the provider's own `usage_metadata`, not from a character heuristic, so the
  figure is what the provider actually charged rather than what we guessed.
* **Cost** - computed from measured tokens and an explicit per-million price.
  The configured provider in this project is Groq's free tier, where the price
  is zero and the honest answer is "no monetary cost, quota-capped"; pass
  `--price-in` / `--price-out` to price the same token counts against a
  commercial endpoint. No price is ever assumed.

End-to-end p50/p95 is reported over whole simulated sessions rather than as a
sum of per-stage medians, because percentiles do not add.

Usage:
    python -m app.eval.latency_eval                    # offline stages only
    python -m app.eval.latency_eval --llm-samples 8    # adds the LLM call
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from app.config import PROJECT_ROOT  # noqa: E402

logger = logging.getLogger(__name__)

OUT_DIR = PROJECT_ROOT / "data" / "eval"
SYNTHETIC_CSV = PROJECT_ROOT / "data" / "stress_dataset.csv"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"
SINGLE_SERIES = "#2a78d6"
ACCENT = "#104281"


@dataclass
class StageTiming:
    """Timings for one pipeline stage, in milliseconds."""

    name: str
    samples: list[float] = field(default_factory=list)
    note: str = ""

    @property
    def p50(self) -> float:
        return statistics.median(self.samples) if self.samples else float("nan")

    @property
    def p95(self) -> float:
        if not self.samples:
            return float("nan")
        if len(self.samples) == 1:
            return self.samples[0]
        return float(pd.Series(self.samples).quantile(0.95))

    @property
    def mean(self) -> float:
        return statistics.fmean(self.samples) if self.samples else float("nan")


def _time_ms(fn, *args, **kwargs) -> float:
    start = time.perf_counter()
    fn(*args, **kwargs)
    return (time.perf_counter() - start) * 1000.0


def measure_cold_start() -> dict[str, float]:
    """Time the one-off model loads with the module caches cleared.

    Reported apart from per-session latency: a process pays this once, and
    folding it into a per-request average would misrepresent both numbers.
    """
    from app.nlp import emotion
    from app.rag import store

    emotion._load_stress_classifier.cache_clear()
    phobert_ms = _time_ms(emotion._load_stress_classifier)

    # The module's own reset entry point, rather than reaching into each cache.
    store.reset_for_tests()
    embedder_ms = _time_ms(store._get_embedding_function)

    return {"phobert_load_ms": phobert_ms, "embedder_load_ms": embedder_ms}


def measure_offline_stages(texts: list[str], repeats: int) -> list[StageTiming]:
    """Time every stage that runs without a network call."""
    from app.api.services import build_rag_query
    from app.eval.baselines import dass_answers_from_row, pss_answers_from_row
    from app.llm.safety import check_crisis
    from app.nlp.emotion import analyze
    from app.nlp.lexicon import find_stress_keywords
    from app.rag.retriever import retrieve
    from app.scoring import score_dass21, score_pss10

    df = pd.read_csv(SYNTHETIC_CSV).head(max(repeats, 1))

    crisis = StageTiming("crisis rule", note="deterministic pattern match (6 constructs); the gate before any side effect")
    lexicon = StageTiming("lexicon keywords", note="210-keyword bilingual stress lexicon")
    phobert = StageTiming("PhoBERT inference", note="skipped on English input by design")
    scoring = StageTiming("DASS-21 + PSS-10 scoring", note="pure arithmetic")
    retrieval = StageTiming("RAG retrieval (k=4)", note="Chroma query + embedding")

    for i in range(repeats):
        text = texts[i % len(texts)]
        row = df.iloc[i % len(df)]

        crisis.samples.append(_time_ms(check_crisis, raw_text=text))
        lexicon.samples.append(_time_ms(find_stress_keywords, text))
        phobert.samples.append(_time_ms(analyze, text))

        dass_answers = dass_answers_from_row(row)
        pss_answers = pss_answers_from_row(row)
        start = time.perf_counter()
        score_dass21(dass_answers)
        score_pss10(pss_answers)
        scoring.samples.append((time.perf_counter() - start) * 1000.0)

        emotion = analyze(text)
        retrieval.samples.append(_time_ms(retrieve, build_rag_query(text, emotion, None), 4))

    return [crisis, lexicon, phobert, scoring, retrieval]


def measure_llm(texts: list[str], samples: int) -> tuple[StageTiming, dict[str, float]]:
    """Time real generation calls and read the provider's own token counts.

    Each sample is a billable request, so this runs only when asked for. Token
    usage is taken from `usage_metadata` when the provider returns it; a
    provider that does not is reported as unmeasured rather than estimated.
    """
    from langchain_core.messages import AIMessage
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    from app.api.services import build_rag_query
    from app.config import get_settings
    from app.llm.chain import HUMAN_PROMPT, SYSTEM_PROMPT, format_retrieved_docs, get_parser
    from app.nlp.emotion import analyze
    from app.rag.retriever import retrieve

    timing = StageTiming("LLM generation", note="network call to the configured provider")
    usage: dict[str, list[int]] = {"input_tokens": [], "output_tokens": []}

    # Deliberately not `build_chain()`: that ends in the parser, which discards
    # the message and with it the provider's usage metadata. The same prompt and
    # the same client settings are used, so the timing is the production call.
    settings = get_settings()
    parser = get_parser()
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)]
    ).partial(format_instructions=parser.get_format_instructions())
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.0,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        max_retries=settings.llm_max_retries,
    )

    for i in range(samples):
        text = texts[i % len(texts)]
        emotion = analyze(text)
        docs = retrieve(build_rag_query(text, emotion, None), k=4)
        rendered = prompt.invoke(
            {
                "raw_text": text,
                "emotion_summary": "(measured run)",
                "questionnaire_summary": "(measured run)",
                "context_summary": "(measured run)",
                "retrieved_docs": format_retrieved_docs(docs),
            }
        )
        start = time.perf_counter()
        try:
            reply = llm.invoke(rendered)
        except Exception as exc:  # noqa: BLE001 - a rate limit must not void the run
            logger.warning("LLM sample %d failed: %s", i + 1, exc)
            continue
        timing.samples.append((time.perf_counter() - start) * 1000.0)

        meta = getattr(reply, "usage_metadata", None) if isinstance(reply, AIMessage) else None
        if meta:
            usage["input_tokens"].append(meta.get("input_tokens", 0))
            usage["output_tokens"].append(meta.get("output_tokens", 0))

    summary = {
        "input_tokens_mean": statistics.fmean(usage["input_tokens"]) if usage["input_tokens"] else float("nan"),
        "output_tokens_mean": statistics.fmean(usage["output_tokens"]) if usage["output_tokens"] else float("nan"),
        "samples_ok": len(timing.samples),
        "samples_requested": samples,
    }
    return timing, summary


def figure_latency(stages: list[StageTiming], out_path: Path) -> Path:
    """Figure 4.9 - per-stage latency, as a p50-to-p95 dot plot.

    Two deliberate choices.

    The axis is logarithmic, because the stages span five orders of magnitude:
    the scoring arithmetic is tens of microseconds and a generation call is
    seconds. On a linear axis every deterministic stage collapses onto the
    baseline and the figure says nothing the table does not.

    The marks are dots, not bars, *because* the axis is logarithmic. A bar
    encodes magnitude as length measured from zero, and a log axis has no zero,
    so bar length there is an artefact of the chosen lower limit - it would show
    the 0.08 ms lexicon stage as roughly half the 65.9 ms classifier. A dot
    encodes by position, which is exactly what a log axis supports, and the
    connector carries the p50-to-p95 spread.
    """
    drawn = sorted([s for s in stages if s.samples], key=lambda s: s.p50)
    names = [s.name for s in drawn]
    p50 = [s.p50 for s in drawn]
    p95 = [s.p95 for s in drawn]
    y = list(range(len(drawn)))

    fig, ax = plt.subplots(figsize=(8.0, 0.62 * len(names) + 2.1))
    fig.patch.set_facecolor(SURFACE)

    for yi, lo, hi in zip(y, p50, p95):
        ax.plot([lo, hi], [yi, yi], color=GRID, linewidth=2, zorder=2, solid_capstyle="round")
    ax.scatter(p95, y, s=90, color=ACCENT, zorder=3,
               edgecolor=SURFACE, linewidth=2, label="p95")
    ax.scatter(p50, y, s=90, color=SINGLE_SERIES, zorder=4,
               edgecolor=SURFACE, linewidth=2, label="p50")

    for yi, lo, hi in zip(y, p50, p95):
        ax.text(hi * 1.5, yi, f"{lo:,.2f} / {hi:,.2f} ms",
                va="center", fontsize=8, color=INK_SECONDARY, zorder=5)

    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_ylim(-0.55, len(names) - 0.30)
    ax.set_xscale("log")
    ax.set_xlim(min(p50) * 0.45, max(p95) * 22)
    ax.set_xlabel("milliseconds (log scale)", color=INK_SECONDARY, fontsize=9)
    ax.set_title("Per-stage latency, p50 to p95", color=INK, fontsize=11, loc="left", pad=12)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9, length=0)
    ax.set_axisbelow(True)
    # Placed in the empty upper-left rather than on the data grid, where a
    # legend row reads as a sixth stage.
    legend = ax.legend(frameon=False, fontsize=9, loc="upper left", ncol=2)
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def _fmt(value: float, digits: int = 2) -> str:
    return "n/a" if pd.isna(value) else f"{value:,.{digits}f}"


def write_markdown(
    stages: list[StageTiming],
    cold: dict[str, float],
    llm_summary: dict[str, float],
    end_to_end: StageTiming,
    price_in: float,
    price_out: float,
    out_path: Path,
) -> Path:
    settings_note = ""
    try:
        from app.config import get_settings

        s = get_settings()
        settings_note = f"`{s.openai_model}` via `{s.openai_base_url or 'api.openai.com'}`"
    except Exception:  # noqa: BLE001
        settings_note = "(provider unavailable)"

    lines = [
        "# Latency and cost",
        "",
        f"Measured {pd.Timestamp.now():%Y-%m-%d} on this machine. Deterministic stages are timed "
        "directly; the generation stage is timed only when samples are requested, because each "
        "sample is a real request.",
        "",
        "## Per-stage latency (ms)",
        "",
        "| Stage | p50 | p95 | mean | n | note |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for stage in stages:
        if not stage.samples:
            lines.append(f"| {stage.name} | not run | not run | not run | 0 | {stage.note} |")
            continue
        lines.append(
            f"| {stage.name} | {_fmt(stage.p50)} | {_fmt(stage.p95)} | {_fmt(stage.mean)} "
            f"| {len(stage.samples)} | {stage.note} |"
        )

    lines += [
        "",
        "## End-to-end session",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    if end_to_end.samples:
        lines += [
            f"| End-to-end p50 | {_fmt(end_to_end.p50)} ms |",
            f"| End-to-end p95 | {_fmt(end_to_end.p95)} ms |",
            f"| Sessions measured | {len(end_to_end.samples)} |",
        ]
    else:
        lines.append("| End-to-end | not measured (no LLM samples requested) |")

    lines += [
        f"| Cold start - PhoBERT load | {_fmt(cold.get('phobert_load_ms', float('nan')))} ms |",
        f"| Cold start - embedder load | {_fmt(cold.get('embedder_load_ms', float('nan')))} ms |",
        "",
        "Cold start is paid once per process, not once per session, so it is listed apart from "
        "the per-session figures rather than averaged into them.",
        "",
        "## Tokens and cost",
        "",
        f"Provider: {settings_note}",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    n_ok = llm_summary.get("samples_ok", 0)
    if n_ok:
        tin = llm_summary["input_tokens_mean"]
        tout = llm_summary["output_tokens_mean"]
        lines += [
            f"| Input tokens per session (mean) | {_fmt(tin, 0)} |",
            f"| Output tokens per session (mean) | {_fmt(tout, 0)} |",
            f"| Total tokens per session (mean) | {_fmt(tin + tout, 0)} |",
        ]
        if price_in or price_out:
            cost = (tin / 1e6) * price_in + (tout / 1e6) * price_out
            lines.append(f"| Cost per session | ${cost:.6f} |")
            lines.append(
                f"| Price applied | ${price_in:.2f}/M in, ${price_out:.2f}/M out |"
            )
        else:
            lines.append("| Cost per session | $0.00 - free tier, quota-capped rather than priced |")
        lines += [
            "",
            "Token counts are the provider's own `usage_metadata`, not a character estimate.",
            f"Measured over {n_ok} of {llm_summary.get('samples_requested', 0)} requested samples.",
        ]
    else:
        lines += [
            "| Tokens per session | not measured |",
            "| Cost per session | not measured |",
            "",
            "No generation samples were requested (`--llm-samples 0`), so the deterministic "
            "stages above are exact and the generation stage is absent. Re-run with "
            "`--llm-samples 8` when provider quota allows.",
        ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def run(repeats: int = 30, llm_samples: int = 0, price_in: float = 0.0,
        price_out: float = 0.0, out_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir) if out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(SYNTHETIC_CSV)
    texts = [str(t) for t in df["free_text"].dropna().head(max(repeats, 1)).tolist()]

    print("Measuring cold start (clearing model caches)")
    cold = measure_cold_start()
    print(f"  PhoBERT load   {cold['phobert_load_ms']:,.0f} ms")
    print(f"  embedder load  {cold['embedder_load_ms']:,.0f} ms")

    print(f"\nMeasuring deterministic stages over {repeats} runs")
    stages = measure_offline_stages(texts, repeats)
    for stage in stages:
        print(f"  {stage.name:28s} p50 {stage.p50:9.3f} ms   p95 {stage.p95:9.3f} ms")

    llm_summary = {"samples_ok": 0, "samples_requested": llm_samples}
    end_to_end = StageTiming("end-to-end session")
    if llm_samples > 0:
        print(f"\nMeasuring {llm_samples} real generation calls")
        llm_timing, llm_summary = measure_llm(texts, llm_samples)
        stages.append(llm_timing)
        if llm_timing.samples:
            print(f"  LLM generation p50 {llm_timing.p50:,.0f} ms   p95 {llm_timing.p95:,.0f} ms")
            # A session is the deterministic path plus one generation call. The
            # deterministic stages are paired with LLM samples by index so the
            # composed sessions are real observations, not a sum of medians.
            deterministic = [s for s in stages if s.name != "LLM generation"]
            for i, llm_ms in enumerate(llm_timing.samples):
                total = llm_ms + sum(
                    s.samples[i % len(s.samples)] for s in deterministic if s.samples
                )
                end_to_end.samples.append(total)
            print(f"  end-to-end     p50 {end_to_end.p50:,.0f} ms   p95 {end_to_end.p95:,.0f} ms")

    md = write_markdown(
        stages, cold, llm_summary, end_to_end, price_in, price_out, out_dir / "latency.md"
    )
    fig = figure_latency(stages, out_dir / "fig_4_9_latency.png")
    payload = {
        "cold_start": cold,
        "stages": {
            s.name: {"p50_ms": s.p50, "p95_ms": s.p95, "mean_ms": s.mean, "n": len(s.samples)}
            for s in stages
            if s.samples
        },
        "end_to_end": (
            {"p50_ms": end_to_end.p50, "p95_ms": end_to_end.p95, "n": len(end_to_end.samples)}
            if end_to_end.samples
            else None
        ),
        "llm": llm_summary,
    }
    (out_dir / "latency.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWrote {md.name}, {fig.name}, latency.json")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure pipeline latency and cost.")
    parser.add_argument("--repeats", type=int, default=30, help="runs per deterministic stage")
    parser.add_argument(
        "--llm-samples", type=int, default=0,
        help="real generation calls to time (each is billable; 0 skips the LLM entirely)",
    )
    parser.add_argument("--price-in", type=float, default=0.0, help="USD per 1M input tokens")
    parser.add_argument("--price-out", type=float, default=0.0, help="USD per 1M output tokens")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    run(
        repeats=args.repeats,
        llm_samples=args.llm_samples,
        price_in=args.price_in,
        price_out=args.price_out,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
