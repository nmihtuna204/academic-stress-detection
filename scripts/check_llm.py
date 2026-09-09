"""Pre-flight check for the configured LLM provider.

Run this the moment you set an API key, before starting an evaluation. It costs
two requests and catches the failures that otherwise only surface partway
through a 400-request run:

1. configuration    - key present, not the placeholder
2. connectivity     - endpoint reachable, key accepted, model id valid
3. JSON adherence   - the real risk with small or free models, because both
                      evaluation systems depend on strict JSON and a model that
                      cannot produce it yields plausible-looking nonsense
4. quota estimate   - how many tokens the pending runs will need

Usage:
    python scripts/check_llm.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PLACEHOLDERS = {"", "sk-...", "sk-xxx", "your-key-here", "changeme"}

# Measured against the real chain and corpus; see docs/RUNNING_LLM_EVAL.md.
TOKENS_PER_ZEROSHOT = 136
TOKENS_PER_FULL = 1793
TEST_ROWS = 70


def _ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def check_config() -> bool:
    from app.config import get_settings

    print("1. Configuration")
    settings = get_settings()

    if settings.openai_api_key.strip() in PLACEHOLDERS:
        _fail("OPENAI_API_KEY is unset or still the placeholder. Edit .env.")
        return False
    _ok(f"API key present ({settings.openai_api_key[:6]}...)")

    endpoint = settings.openai_base_url or "https://api.openai.com/v1 (default)"
    _ok(f"endpoint: {endpoint}")
    _ok(f"model:    {settings.openai_model}")
    _ok(f"concurrency: {settings.llm_concurrency}")

    if settings.openai_base_url and "openai.com" not in settings.openai_base_url:
        print()
        print("  NOTE: you are not using OpenAI. Before collecting REAL participant")
        print("        data, update docs/consent_form_vi.md §4, the consent list in")
        print("        streamlit_app/Home.py, and the report, all of which name OpenAI.")
        print("        The report must also name the model you actually used.")
    return True


def check_connectivity() -> object | None:
    from app.config import get_settings

    print("\n2. Connectivity")
    settings = get_settings()
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            timeout=30,
            temperature=0.0,
        )
        reply = llm.invoke("Reply with exactly: OK")
    except Exception as exc:  # noqa: BLE001 - the diagnosis is the point
        _fail(f"{type(exc).__name__}: {exc}")
        print("\n  Common causes:")
        print("    401 / AuthenticationError -> key wrong, or key not valid for this endpoint")
        print("    404 / NotFoundError       -> model id not offered here, or base URL missing /v1")
        print("    Connection refused        -> local server not running (ollama serve)")
        print("    429                       -> rate limited; lower LLM_CONCURRENCY")
        return None

    _ok(f"reachable, replied: {reply.content.strip()[:40]!r}")
    return llm


def check_json_adherence(llm) -> bool:
    """The evaluation depends on strict JSON; a model that cannot is unusable.

    On a parse failure the zero-shot harness falls back to predicting "Moderate"
    and counts the failure, so a model that fails often produces a metric that
    looks reasonable and means nothing. Better to find out now.
    """
    from app.eval.baselines import ZEROSHOT_SYSTEM, _parse_label_json

    print("\n3. Strict-JSON adherence (the usual failure with small/free models)")
    from langchain_core.messages import HumanMessage, SystemMessage

    sample = (
        "This week I have been overwhelmed by deadlines, I sleep about four hours "
        "a night and I cannot concentrate on anything."
    )
    try:
        reply = llm.invoke(
            [SystemMessage(content=ZEROSHOT_SYSTEM), HumanMessage(content=sample)]
        )
    except Exception as exc:  # noqa: BLE001
        _fail(f"request failed: {type(exc).__name__}: {exc}")
        return False

    label, confidence = _parse_label_json(reply.content)
    if label is None:
        _fail("reply did not parse as the required JSON object")
        print(f"         raw reply: {reply.content.strip()[:200]!r}")
        print("         This model will inflate parse_failures. Try a larger one.")
        return False

    _ok(f"parsed cleanly: label={label} confidence={confidence}")
    return True


def report_quota() -> bool:
    """Report what the pending runs need and what the provider says is left.

    Returns True only when a `compare` run can be expected to finish. The old
    version printed an arithmetic estimate and nothing about actual headroom,
    which is how a run was started on 2026-09-09 with 485 tokens left in the
    day's allowance.
    """
    from app.config import get_settings
    from app.eval.quota import (
        estimate_run_tokens,
        load_daily_quota,
        probe_headers,
        verdict,
    )

    print("\n4. Quota estimate for the pending runs (input tokens, approximate)")
    zeroshot = TEST_ROWS * TOKENS_PER_ZEROSHOT
    full = TEST_ROWS * TOKENS_PER_FULL
    ablation_rest = 4 * TEST_ROWS * TOKENS_PER_FULL * 0.8  # 2 configs omit the docs

    rows = [
        ("compare: llm_zeroshot", TEST_ROWS, zeroshot),
        ("compare: llm_full", TEST_ROWS, full),
        ("ablation: 4 further configs", 4 * TEST_ROWS, ablation_rest),
    ]
    print(f"  {'run':32s} {'requests':>9s} {'tokens':>10s}")
    for name, reqs, toks in rows:
        print(f"  {name:32s} {reqs:9d} {toks:10,.0f}")
    total_reqs = sum(r for _, r, _ in rows)
    total_toks = sum(t for _, _, t in rows)
    print(f"  {'TOTAL':32s} {total_reqs:9d} {total_toks:10,.0f}")
    print()
    print("  The disk cache makes runs resumable: re-run the same command the")
    print("  next day and it continues where the quota stopped it.")
    print("  Run `compare` first - the ablation's `full` config reuses its cache.")

    settings = get_settings()
    print("\n5. Provider rate-limit headers (what the API actually reports)")
    headers, status = probe_headers(
        settings.openai_model, settings.openai_api_key, settings.openai_base_url
    )
    if not headers:
        print(f"  [--]   no rate-limit headers returned (probe status: {status})")
    else:
        for key, value in headers.items():
            print(f"  {key:32s} {value}")
        print()
        print("  READ THESE CAREFULLY: on Groq the *token* headers are the per-MINUTE")
        print("  bucket and the *request* headers are the per-DAY bucket. Neither one")
        print("  reports tokens per day, which is the limit that stops a long run.")

    print("\n6. Daily token allowance (the limit that actually blocks a run)")
    quota = load_daily_quota()
    if quota is None:
        print("  [--]   unknown - no 429 recorded yet; the provider exposes this")
        print("         figure only in the body of a rate-limit error.")
    else:
        print(f"  limit      {quota.limit:,}")
        print(f"  used       {quota.used:,}")
        print(f"  remaining  {quota.remaining:,}")
        print(f"  observed   {quota.observed_at}  ({quota.age_hours:.1f} h ago)")
        if quota.retry_after:
            print(f"  retry hint {quota.retry_after}")

    needed = estimate_run_tokens(TEST_ROWS, TOKENS_PER_FULL)
    can_run, why = verdict(needed, quota)
    print()
    print(f"  {'[ok]  ' if can_run else '[STOP]'} {why}")
    return can_run


def main() -> None:
    print("LLM provider pre-flight\n" + "=" * 55)

    if not check_config():
        sys.exit(1)

    llm = check_connectivity()
    if llm is None:
        sys.exit(1)

    json_ok = check_json_adherence(llm)
    quota_ok = report_quota()

    print("\n" + "=" * 55)
    if json_ok and quota_ok:
        print("Ready. Next: python -m app.eval.compare --dataset synthetic")
        print("See docs/RUNNING_LLM_EVAL.md for the full sequence.")
    elif json_ok:
        print("Connection and JSON adherence are fine, but the daily token")
        print("allowance does not look sufficient - see section 6 above.")
        print("Starting anyway is safe (the run resumes from cache), it just")
        print("will not finish. This is NOT the same as ready.")
        sys.exit(2)
    else:
        print("Connection works but JSON adherence failed. Change OPENAI_MODEL")
        print("before running any evaluation, or the numbers will be meaningless.")
        sys.exit(1)


if __name__ == "__main__":
    main()
