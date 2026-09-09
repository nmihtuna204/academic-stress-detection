"""Tests for the real-data collection toolkit (export + quality report)."""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import data_quality_report  # noqa: E402
import export_dataset  # noqa: E402

from app.db import QuestionnaireResponse, TextEntry, User, get_session  # noqa: E402
from app.eval.synthetic import seed_database  # noqa: E402


@pytest.fixture()
def seeded_db(tmp_db):
    seed_database(rows=24, seed=11)
    yield


class TestExport:
    def test_exports_all_labeled_rows_without_identifying_fields(self, seeded_db):
        rows = export_dataset.collect_rows()
        assert len(rows) == 24
        first = rows[0]
        for banned in ("age", "gender", "major", "university", "year_of_study"):
            assert banned not in first
        assert first["label"] in ("Low", "Moderate", "High", "Severe")
        assert "dass21_q1" in first and "pss_q10" in first

    def test_students_without_questionnaire_are_skipped(self, seeded_db):
        session = next(get_session())
        try:
            session.add(User(age=20))  # user with no responses at all
            session.commit()
        finally:
            session.close()
        assert len(export_dataset.collect_rows()) == 24

    def test_split_is_stratified_and_deterministic(self, seeded_db):
        import pandas as pd

        df = pd.DataFrame(export_dataset.collect_rows())
        split1 = export_dataset.add_split(df, seed=42)
        split2 = export_dataset.add_split(df, seed=42)
        assert (split1["split"] == split2["split"]).all()
        assert set(split1["split"].unique()) == {"train", "test"}
        assert (split1["split"] == "test").sum() == round(len(df) * 0.2)

    def test_summary_reports_missing_text(self, seeded_db):
        import pandas as pd

        df = pd.DataFrame(export_dataset.collect_rows())
        summary = export_dataset.summarize(df)
        assert "missing free text:    24" in summary


class TestQualityReport:
    def make_user(self, session, dass_value=None, pss_values=None, text=None,
                  minutes_elapsed=10.0, dass_level=None, pss_cat=None) -> str:
        user = User(age=20)
        session.add(user)
        session.flush()
        response = QuestionnaireResponse(student_id=user.student_id)
        if dass_value is not None:
            for i in range(1, 22):
                setattr(response, f"dass_q{i}", dass_value)
        if pss_values is not None:
            for i in range(1, 11):
                setattr(response, f"pss_q{i}", pss_values)
        response.stress_level_dass = dass_level
        response.pss_stress_category = pss_cat
        response.created_at = user.created_at + timedelta(minutes=minutes_elapsed)
        session.add(response)
        if text is not None:
            session.add(
                TextEntry(student_id=user.student_id, raw_text=text, text_length=len(text))
            )
        session.commit()
        return user.student_id

    def test_straight_lining_flagged(self, tmp_db):
        session = next(get_session())
        try:
            sid = self.make_user(session, dass_value=2, pss_values=3,
                                 text="word " * 30)
            user = session.get(User, sid)
            response = user.questionnaire_responses[0]
            flags = data_quality_report.check_student(user, response, user.text_entries[0])
            assert "straight_line_dass" in flags
            assert "straight_line_pss" in flags
        finally:
            session.close()

    def test_short_text_and_fast_completion_flagged(self, tmp_db):
        session = next(get_session())
        try:
            sid = self.make_user(session, dass_value=None, text="too short",
                                 minutes_elapsed=0.5)
            user = session.get(User, sid)
            flags = data_quality_report.check_student(
                user, user.questionnaire_responses[0], user.text_entries[0]
            )
            assert any(f.startswith("short_text") for f in flags)
            assert any(f.startswith("fast_completion") for f in flags)
        finally:
            session.close()

    def test_dass_pss_mismatch_flagged(self, tmp_db):
        session = next(get_session())
        try:
            sid = self.make_user(session, text="word " * 25,
                                 dass_level="Extremely Severe", pss_cat="Low")
            user = session.get(User, sid)
            flags = data_quality_report.check_student(
                user, user.questionnaire_responses[0], user.text_entries[0]
            )
            assert any(f.startswith("dass_pss_mismatch") for f in flags)
        finally:
            session.close()

    def test_clean_submission_not_flagged(self, tmp_db):
        session = next(get_session())
        try:
            # Varied answers, long text, plausible timing, consistent levels.
            user = User(age=20)
            session.add(user)
            session.flush()
            response = QuestionnaireResponse(student_id=user.student_id)
            for i in range(1, 22):
                setattr(response, f"dass_q{i}", i % 4)
            for i in range(1, 11):
                setattr(response, f"pss_q{i}", i % 5)
            response.stress_level_dass = "Moderate"
            response.pss_stress_category = "Moderate"
            response.created_at = user.created_at + timedelta(minutes=12)
            session.add(response)
            entry = TextEntry(
                student_id=user.student_id,
                raw_text="this week I studied a lot but I am still okay " * 4,
                text_length=100,
            )
            session.add(entry)
            session.commit()
            flags = data_quality_report.check_student(user, response, entry)
            assert flags == []
        finally:
            session.close()
