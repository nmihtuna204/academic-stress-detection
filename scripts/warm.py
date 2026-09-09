"""Warm every lazily-loaded component before a demo or a presentation.

The first request to a cold process pays ~25 s: PhoBERT (~8 s) and the
sentence-transformers embedder (~11 s) both load on first use, by design -
loading them in the API startup hook would block the port for half a minute.
That trade is right for a server and wrong for a live demo, where 25 s of blank
screen in front of an audience is the worst possible moment to discover it.

This script pays that cost deliberately, then verifies the whole path end to
end: health -> PhoBERT -> Chroma retrieval -> generation. It reports which
stages are actually live, so "the LLM is out of quota" is something you learn
here rather than on stage.

Usage:
    python scripts/warm.py                    # assumes API on 127.0.0.1:8000
    python scripts/warm.py --port 8000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def _post(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    base = f"http://{args.host}:{args.port}"

    print("Warming the pipeline (first call loads both models - expect ~25 s)\n")

    # --- 1. health: loads the embedder via the Chroma collection count -------
    start = time.time()
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=args.timeout) as resp:
            health = json.load(resp)
    except urllib.error.URLError as exc:
        print(f"  [FAIL] cannot reach {base}/health - is the API running?")
        print(f"         {exc}")
        return 1
    print(f"  [ok]   health            {time.time() - start:5.1f}s   {health}")

    chunks = health.get("knowledge_chunks", 0)
    if chunks == 0:
        print("\n  [FAIL] knowledge base is EMPTY. Retrieval will return nothing and the")
        print("         generator will refuse to answer. Fix with:  python -m app.rag.ingest")
        return 1

    # --- 2. full assessment: PhoBERT + retrieval + generation ----------------
    # Items 17 and 21 are the DASS-21 risk items; they are held at 0 so this
    # warm-up exercises the NORMAL path rather than tripping the crisis rule
    # and short-circuiting before retrieval and generation.
    answers = {str(i): 2 for i in range(1, 22)}
    answers["17"] = 0
    answers["21"] = 0
    payload = {
        "raw_text": "I cannot sleep before exams and I feel like I am falling behind.",
        "dass21": {"answers": answers},
        "pss10": {"answers": {str(i): 3 for i in range(1, 11)}},
        "stress_context": {"sleep_hours_avg": 4.5, "is_exam_period": True},
    }
    start = time.time()
    try:
        result = _post(f"{base}/assess/full", payload, args.timeout)
    except Exception as exc:  # noqa: BLE001 - the diagnosis is the point
        print(f"  [FAIL] /assess/full raised {type(exc).__name__}: {exc}")
        return 1
    elapsed = time.time() - start

    if result.get("crisis_detected"):
        print("  [FAIL] the warm-up input tripped the crisis rule - it should not.")
        return 1

    label = (result.get("questionnaire") or {}).get("ground_truth_label")
    sources = len(result.get("rag_sources") or [])
    has_llm = result.get("assessment") is not None

    print(f"  [ok]   PhoBERT + scoring {elapsed:5.1f}s   headline label: {label}")
    print(f"  [ok]   retrieval                   {sources} passages")
    if has_llm:
        print("  [ok]   generation                  advice present, citations verified")
    else:
        reason = result.get("advice_unavailable_reason") or "(no reason given)"
        print(f"  [WARN] generation                  NOT available - {reason}")

    # --- 3. prove it is actually warm now ------------------------------------
    start = time.time()
    with urllib.request.urlopen(f"{base}/health", timeout=30):
        pass
    second = time.time() - start
    print(f"\n  second health call: {second:.2f}s", end="  ")
    print("(warm)" if second < 1.0 else "(STILL COLD - something is reloading)")

    print("\nReady." if has_llm else "\nReady, but generation is unavailable - see docs/RUNNING_LLM_EVAL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
