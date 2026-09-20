"""Faithfulness judge harness: parsing, intervals, and an end-to-end stub run."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from app.eval import faithfulness_eval as fe
from app.rag.retriever import RetrievedDoc


def reply(*verdicts: str) -> str:
    return json.dumps(
        {
            "verdicts": [
                {"i": i, "verdict": v, "evidence": ["02.md::0"], "reason": "r"}
                for i, v in enumerate(verdicts, start=1)
            ]
        }
    )


class TestParseVerdicts:
    def test_one_verdict_per_suggestion_in_order(self):
        parsed = fe.parse_verdicts(reply("supported", "unsupported"), 2)
        assert [p["verdict"] for p in parsed] == ["supported", "unsupported"]

    def test_reasoning_scratchpad_is_stripped(self):
        parsed = fe.parse_verdicts("<think>hmm {not json}</think>" + reply("partial"), 1)
        assert parsed[0]["verdict"] == "partial"

    def test_a_skipped_suggestion_rejects_the_whole_reply(self):
        """Filling a gap with any verdict would bias the rate towards it."""
        assert fe.parse_verdicts(reply("supported"), 2) is None

    def test_an_invented_label_rejects_the_whole_reply(self):
        assert fe.parse_verdicts(reply("mostly_supported"), 1) is None

    def test_prose_without_json_is_unusable(self):
        assert fe.parse_verdicts("All of them are supported.", 1) is None


class TestRefusalDetection:
    """Refusals written into the suggestions field are not advice to be judged."""

    @pytest.mark.parametrize(
        "text",
        [  # verbatim from the 2026-09-19 no_rag run
            "No specific coping suggestions are available from the reference material.",
            "No specific coping suggestions are available from the provided reference material.",
            "No specific coping suggestions can be provided based on the available reference material.",
        ],
    )
    def test_observed_refusals_are_recognised(self, text):
        assert fe.is_refusal(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Consider reaching out to your university's counseling or health services.",
            "Use the Pomodoro technique: 25 minutes of study, then a 5-minute break.",
            "Keep no screens in bed for 30 minutes before sleep.",
        ],
    )
    def test_real_advice_is_not_mistaken_for_a_refusal(self, text):
        assert not fe.is_refusal(text)


class TestReferralDetection:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Consider reaching out to your university counselling office.", True),
            ("If insomnia lasts three weeks, get checked by a health professional.", True),
            ("Use the Pomodoro technique for 25-minute study blocks.", False),
            ("Talk to a trusted friend about how you feel.", False),
        ],
    )
    def test_referral_detection(self, text, expected):
        assert fe.is_referral(text) is expected


class TestWilson:
    def test_interval_contains_the_point_estimate(self):
        lo, hi = fe.wilson(30, 40)
        assert lo < 0.75 < hi

    def test_empty_sample(self):
        assert fe.wilson(0, 0) == (0.0, 0.0)

    def test_all_successes_does_not_collapse_to_a_point(self):
        lo, hi = fe.wilson(10, 10)
        assert hi == 1.0 and lo < 0.8


class TestRun:
    """End to end on a stub judge, with every cache write kept in tmp_path."""

    @pytest.fixture()
    def stubbed(self, tmp_path, monkeypatch):
        import app.api.services as services
        import app.nlp.emotion as emotion
        from app.eval import baselines
        from app.eval.ablation import subsample_test_split
        from app.eval.datasets import load_eval_dataset

        doc = RetrievedDoc(text="Sleep 7-8 hours.", source="04.md", heading="Sleep",
                           distance=0.1, chunk_id="04.md::0")
        monkeypatch.setattr(services, "retrieve", lambda query, k=4: [doc])
        monkeypatch.setattr(services, "fetch_chunks", lambda ids: [])
        monkeypatch.setattr(emotion, "analyze", lambda text: None)

        test = subsample_test_split(load_eval_dataset("synthetic", out_dir=tmp_path), 6)
        test = test[test["split"] == "test"]
        cache = tmp_path / "cache"
        for n, (_, row) in enumerate(test.iterrows()):
            full_key, _, _ = baselines.full_cache_key(row, True, True, True)
            baselines.cache_put(cache, full_key, {"label": "High", "suggestions": ["Sleep more.", "Rest."]})
            # The control declines on the first item and advises on the rest.
            rag_key, _, _ = baselines.full_cache_key(row, False, True, True)
            baselines.cache_put(cache, rag_key, {"label": "High", "suggestions": [] if n == 0 else ["Run."]})

        class StubJudge:
            """Answers by content, since concurrent calls arrive in no fixed order."""

            async def ainvoke(self, messages):
                if "Sleep more." in messages[-1].content:
                    return AIMessage(content=reply("supported", "partial"))
                return AIMessage(content=reply("unsupported"))

        monkeypatch.setattr(fe, "_judge_llm", lambda model: StubJudge())
        return tmp_path, cache, len(test)

    def test_arms_are_counted_and_declines_are_not_judged(self, stubbed):
        tmp_path, cache, n = stubbed
        table = fe.run(limit=6, judge_model="stub", out_dir=tmp_path, cache_dir=cache).set_index("arm")

        assert table.loc["full", "items_generated"] == n
        assert table.loc["full", "suggestions"] == 2 * n
        assert table.loc["no_rag", "items_declined"] == 1
        assert table.loc["no_rag", "suggestions"] == n - 1
        assert (tmp_path / "faithfulness_eval.md").exists()
        detail = (tmp_path / "faithfulness_judgments.csv").read_text(encoding="utf-8")
        assert "passages" in detail, "the rating sheet is built from these"

    def test_agreement_reads_only_rated_rows(self, tmp_path):
        import pandas as pd

        pd.DataFrame(
            {
                "verdict": ["supported", "unsupported", "partial"],
                "human_verdict": ["supported", "unsupported", ""],
            }
        ).to_csv(tmp_path / "j.csv", index=False)
        message = fe.agreement(tmp_path / "j.csv")
        assert "2 suggestions" in message and "raw 100.0%" in message


class TestRatingSheet:
    """The human rates blind; the key joins the judge back in afterwards."""

    def _judgments(self, tmp_path):
        import pandas as pd

        rows = [
            {"item": i, "arm": "full", "index": 1, "suggestion": f"s{i}", "verdict": v,
             "passages": f"[p{i}] text"}
            for i, v in enumerate(["supported"] * 8 + ["partial"] * 3 + ["unsupported"])
        ]
        path = tmp_path / "judgments.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        return path

    def test_sheet_hides_the_judge_and_covers_every_verdict(self, tmp_path):
        import pandas as pd

        sheet, key = tmp_path / "sheet.csv", tmp_path / "key.csv"
        n = fe.export_rating_sheet(6, judgments_csv=self._judgments(tmp_path), sheet=sheet, key=key)
        blind = pd.read_csv(sheet)
        assert n == 6 and len(blind) == 6
        assert "verdict" not in blind.columns, "the rater must not see the judge's verdict"
        assert set(pd.read_csv(key)["verdict"]) == {"supported", "partial", "unsupported"}

    def test_agreement_joins_the_key(self, tmp_path):
        import pandas as pd

        sheet, key = tmp_path / "sheet.csv", tmp_path / "key.csv"
        fe.export_rating_sheet(6, judgments_csv=self._judgments(tmp_path), sheet=sheet, key=key)
        blind = pd.read_csv(sheet)
        truth = pd.read_csv(key).set_index("row_id")["verdict"]
        blind["human_verdict"] = blind["row_id"].map(truth)  # a rater who agrees exactly
        blind.to_csv(sheet, index=False)
        assert "raw 100.0%" in fe.agreement(sheet, key)
