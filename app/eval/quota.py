"""Provider quota accounting for the evaluation runs.

Why this exists. On 2026-09-09 a pre-flight check reported the provider
reachable and JSON adherence fine, and an evaluation run was started on that
basis. It failed after four items: the daily token allowance had been consumed
the previous day and only ~500 tokens remained. The pre-flight had spent about
200 tokens, which fit in that gap, so "it worked" proved nothing about whether
88,000 tokens were available.

The obvious fix - read `x-ratelimit-remaining-tokens` - does not work either,
and it is worth being explicit about why, because the header looks like the
answer. Measured against Groq:

    x-ratelimit-limit-tokens       = 8000     per MINUTE (TPM)
    x-ratelimit-remaining-tokens   = 7927     remaining THIS MINUTE
    x-ratelimit-limit-requests     = 1000     per DAY (RPD)
    x-ratelimit-remaining-requests = 998      remaining today

The token header tracks the per-minute bucket; the request header tracks the
daily one. The limit that actually blocks a long evaluation - tokens per day -
is exposed in no header at all. Reading the token header would have returned
"7,927 remaining" at the exact moment the account was at 199,515 of 200,000 for
the day.

The daily figure IS available, but only inside the body of a 429:

    Rate limit reached ... on tokens per day (TPD):
    Limit 200000, Used 199515, Requested 3150

So that is what this module captures. When a run hits a 429, the provider's own
daily numbers are parsed and persisted with a timestamp. The pre-flight then
reports the last authoritative reading and how old it is, instead of inferring
headroom from a request small enough to fit through any gap.

The ledger is a record of what the provider said, never an estimate. If nothing
has been recorded, the pre-flight says the daily figure is unknown - which is
the honest answer and the one that would have prevented the failed run.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

STATE_PATH = PROJECT_ROOT / "data" / "eval" / "quota_state.json"

# "on tokens per day (TPD): Limit 200000, Used 199515, Requested 3150"
_TPD_RE = re.compile(
    r"tokens?\s+per\s+day\s*\(?(?:TPD)?\)?\s*:?\s*Limit\s+(\d+),\s*Used\s+(\d+),\s*Requested\s+(\d+)",
    re.IGNORECASE,
)
# Fallback: any "Limit N, Used N, Requested N" triple, used only when the
# message names a daily bucket somewhere.
_GENERIC_RE = re.compile(r"Limit\s+(\d+),\s*Used\s+(\d+),\s*Requested\s+(\d+)", re.IGNORECASE)
_RETRY_RE = re.compile(r"try again in ([0-9hms.]+)", re.IGNORECASE)


@dataclass
class DailyTokenQuota:
    """The provider's own daily-token figures, as reported in a 429."""

    limit: int
    used: int
    requested: int
    retry_after: str | None
    observed_at: str

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)

    @property
    def age_hours(self) -> float:
        seen = datetime.fromisoformat(self.observed_at)
        return (datetime.now(timezone.utc) - seen).total_seconds() / 3600.0


def parse_daily_quota(message: str) -> DailyTokenQuota | None:
    """Extract the daily-token figures from a 429 body, or None.

    Returns None rather than guessing when the message describes a per-minute
    limit: a TPM refusal says nothing about the day's remaining allowance, and
    recording it as if it did would recreate the original error.
    """
    if not message:
        return None
    match = _TPD_RE.search(message)
    if match is None:
        daily_mentioned = re.search(r"per\s+day|TPD", message, re.IGNORECASE)
        generic = _GENERIC_RE.search(message)
        if not (daily_mentioned and generic):
            return None
        match = generic
    retry = _RETRY_RE.search(message)
    return DailyTokenQuota(
        limit=int(match.group(1)),
        used=int(match.group(2)),
        requested=int(match.group(3)),
        retry_after=retry.group(1).rstrip(".") if retry else None,
        observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def record_daily_quota(quota: DailyTokenQuota, path: Path | None = None) -> None:
    """Persist the newest reading; diagnostics must never break a run."""
    path = path or STATE_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(quota), indent=1), encoding="utf-8")
    except OSError as exc:
        logger.warning("could not record quota state: %s", exc)


def record_from_error(exc: BaseException, path: Path | None = None) -> DailyTokenQuota | None:
    """Parse and persist daily figures from a provider exception, if present."""
    quota = parse_daily_quota(str(exc))
    if quota is not None:
        record_daily_quota(quota, path)
    return quota


def load_daily_quota(path: Path | None = None) -> DailyTokenQuota | None:
    path = path or STATE_PATH
    try:
        return DailyTokenQuota(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def read_rate_limit_headers(headers) -> dict[str, str]:
    """Pull the provider's rate-limit headers out of a response.

    Reported for what they are - a per-minute token bucket and a per-day
    request bucket - and never as the daily token allowance, which they do not
    describe.
    """
    if not headers:
        return {}
    wanted = (
        "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-tokens",
        "x-ratelimit-reset-tokens",
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
    )
    out: dict[str, str] = {}
    for key in wanted:
        try:
            value = headers.get(key)
        except AttributeError:
            continue
        if value is not None:
            out[key] = str(value)
    return out


def probe_headers(model: str, api_key: str, base_url: str | None) -> tuple[dict[str, str], str]:
    """Send the smallest possible request and return its rate-limit headers.

    One token of output, so the cost is negligible. A 429 is not a failure
    here - its headers and body are exactly what we came for - so the daily
    figures are recorded from it when present.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url or None, max_retries=0)
    try:
        raw = client.chat.completions.with_raw_response.create(
            model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=1
        )
        return read_rate_limit_headers(raw.headers), "ok"
    except Exception as exc:  # noqa: BLE001 - a 429 here is information, not an error
        record_from_error(exc)
        headers = getattr(getattr(exc, "response", None), "headers", None)
        return read_rate_limit_headers(headers), type(exc).__name__


def estimate_run_tokens(rows: int, tokens_per_row: int) -> int:
    return rows * tokens_per_row


def verdict(needed: int, quota: DailyTokenQuota | None) -> tuple[bool, str]:
    """Decide whether a run of `needed` tokens should be started.

    Unknown is not treated as fine. The failure this module exists to prevent
    came from treating an absence of evidence as headroom.
    """
    if quota is None:
        return False, (
            "The daily token allowance is UNKNOWN - no 429 has been recorded yet, and no "
            "provider header reports it. Connectivity alone does not establish headroom: a "
            "200-token probe fits through a 500-token gap. Either start the run knowing it "
            "may stop early (the disk cache makes it resumable) or run a small job first to "
            "learn the daily figure."
        )
    if quota.age_hours > 18:
        return True, (
            f"Last daily reading is {quota.age_hours:.0f} h old ({quota.used:,}/{quota.limit:,} "
            "used) and almost certainly stale - the allowance has likely rolled over since. "
            "Treat as probably fine, but expect the run to tell you the truth."
        )
    if quota.remaining >= needed:
        return True, (
            f"{quota.remaining:,} tokens remained {quota.age_hours:.1f} h ago; this run needs "
            f"about {needed:,}."
        )
    shortfall = needed - quota.remaining
    retry = f" Provider suggested retrying in {quota.retry_after}." if quota.retry_after else ""
    return False, (
        f"Only {quota.remaining:,} of {quota.limit:,} daily tokens remained "
        f"{quota.age_hours:.1f} h ago, and this run needs about {needed:,} - short by roughly "
        f"{shortfall:,}.{retry} Completed items stay cached, so a later re-run resumes rather "
        "than restarts."
    )
