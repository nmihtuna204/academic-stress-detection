"""Tests for provider quota accounting.

These lock in the distinction that caused a wasted evaluation run: the
provider's rate-limit *headers* describe a per-minute token bucket, while the
limit that stops a long run is tokens per day, which appears only inside the
body of a 429.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.eval.quota import (
    DailyTokenQuota,
    load_daily_quota,
    parse_daily_quota,
    read_rate_limit_headers,
    record_daily_quota,
    record_from_error,
    verdict,
)

# The real message, verbatim from the 2026-09-09 run.
REAL_429 = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "`openai/gpt-oss-120b` in organization `org_01m1` service tier `on_demand` on "
    "tokens per day (TPD): Limit 200000, Used 199515, Requested 3150. Please try "
    "again in 2m23.424s. Need more tokens? Upgrade to Dev Tier today', "
    "'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
)

# A per-minute refusal. Recording this as a daily figure would recreate the bug.
TPM_429 = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "`openai/gpt-oss-120b` on tokens per minute (TPM): Limit 8000, Used 7900, "
    "Requested 300. Please try again in 1.5s.', 'code': 'rate_limit_exceeded'}}"
)


class TestParsing:
    def test_daily_figures_are_extracted(self):
        quota = parse_daily_quota(REAL_429)
        assert quota is not None
        assert quota.limit == 200_000
        assert quota.used == 199_515
        assert quota.requested == 3_150
        assert quota.remaining == 485
        assert quota.retry_after == "2m23.424s"

    def test_per_minute_refusal_is_not_recorded_as_daily(self):
        """A TPM refusal says nothing about the day's remaining allowance."""
        assert parse_daily_quota(TPM_429) is None

    def test_unrelated_text_yields_nothing(self):
        assert parse_daily_quota("Connection reset by peer") is None
        assert parse_daily_quota("") is None

    def test_remaining_never_goes_negative(self):
        quota = DailyTokenQuota(
            limit=100, used=140, requested=10, retry_after=None,
            observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        assert quota.remaining == 0


class TestHeaders:
    def test_only_rate_limit_headers_are_kept(self):
        headers = {
            "x-ratelimit-limit-tokens": "8000",
            "x-ratelimit-remaining-tokens": "7927",
            "x-ratelimit-remaining-requests": "998",
            "content-type": "application/json",
            "authorization": "secret",
        }
        out = read_rate_limit_headers(headers)
        assert out["x-ratelimit-remaining-tokens"] == "7927"
        assert "authorization" not in out
        assert "content-type" not in out

    def test_missing_headers_are_tolerated(self):
        assert read_rate_limit_headers(None) == {}
        assert read_rate_limit_headers({}) == {}


class TestPersistence:
    def test_roundtrip(self, tmp_path):
        path = tmp_path / "quota.json"
        quota = parse_daily_quota(REAL_429)
        record_daily_quota(quota, path)
        loaded = load_daily_quota(path)
        assert loaded is not None
        assert loaded.used == 199_515

    def test_missing_or_corrupt_state_is_unknown_not_a_crash(self, tmp_path):
        assert load_daily_quota(tmp_path / "absent.json") is None
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert load_daily_quota(bad) is None
        wrong_shape = tmp_path / "wrong.json"
        wrong_shape.write_text(json.dumps({"unexpected": 1}), encoding="utf-8")
        assert load_daily_quota(wrong_shape) is None

    def test_record_from_error_persists_only_daily_refusals(self, tmp_path):
        path = tmp_path / "quota.json"
        assert record_from_error(RuntimeError(TPM_429), path) is None
        assert not path.exists()
        assert record_from_error(RuntimeError(REAL_429), path) is not None
        assert path.exists()


def _quota(used: int, hours_ago: float = 0.0) -> DailyTokenQuota:
    seen = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return DailyTokenQuota(
        limit=200_000, used=used, requested=0, retry_after=None,
        observed_at=seen.isoformat(timespec="seconds"),
    )


class TestVerdict:
    def test_unknown_quota_does_not_give_a_green_light(self):
        """The original failure was treating absence of evidence as headroom."""
        can_run, why = verdict(125_510, None)
        assert can_run is False
        assert "UNKNOWN" in why

    def test_insufficient_headroom_stops_the_run(self):
        can_run, why = verdict(125_510, _quota(used=199_515))
        assert can_run is False
        assert "485" in why
        assert "resumes" in why

    def test_ample_headroom_allows_the_run(self):
        can_run, why = verdict(125_510, _quota(used=1_000))
        assert can_run is True
        assert "199,000" in why

    def test_a_stale_reading_is_treated_as_probably_rolled_over(self):
        can_run, why = verdict(125_510, _quota(used=199_515, hours_ago=20))
        assert can_run is True
        assert "stale" in why

    def test_the_boundary_is_the_amount_actually_needed(self):
        assert verdict(1_000, _quota(used=199_000))[0] is True   # exactly 1,000 left
        assert verdict(1_001, _quota(used=199_000))[0] is False
