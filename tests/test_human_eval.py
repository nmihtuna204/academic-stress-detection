"""Tests for the human-evaluation scaffolding (rating export/analysis, SUS)."""

import numpy as np
import pandas as pd
import pytest

from app.eval.export_for_rating import sample_explanations, write_sheets
from app.eval.rating_analysis import analyze, krippendorff_alpha, load_sheets
from app.eval.sus_score import grade, score_file, sus_score


class TestExportForRating:
    def seed_predictions(self, n=10, explanation="Giải thích thật của mô hình."):
        from app.db import Prediction, User, get_session

        session = next(get_session())
        try:
            for i in range(n):
                user = User(age=20)
                session.add(user)
                session.flush()
                session.add(
                    Prediction(
                        student_id=user.student_id,
                        ground_truth_label="Moderate",
                        llm_predicted_label="Moderate",
                        llm_explanation=f"{explanation} #{i}",
                    )
                )
            session.commit()
        finally:
            session.close()

    def test_refuses_synthetic_placeholders(self, tmp_db):
        self.seed_predictions(n=5, explanation="(synthetic")  # only near-placeholder
        from app.db import get_session, Prediction

        session = next(get_session())
        try:
            for p in session.query(Prediction).all():
                p.llm_explanation = "(synthetic)"
            session.commit()
        finally:
            session.close()
        with pytest.raises(SystemExit, match="synthetic"):
            sample_explanations(n=5)

    def test_sheets_share_items_in_different_order(self, tmp_db, tmp_path):
        self.seed_predictions(n=12)
        items = sample_explanations(n=10, seed=1)
        assert len(items) == 10
        paths = write_sheets(items, raters=3, out_dir=tmp_path, seed=1)
        assert len(paths) == 3
        sheets = [pd.read_csv(p, encoding="utf-8-sig") for p in paths]
        id_sets = [set(s["item_id"]) for s in sheets]
        assert id_sets[0] == id_sets[1] == id_sets[2]
        # Scoring columns exist and are blank.
        for sheet in sheets:
            assert sheet["accuracy_1_5"].isna().all()
            assert "comment" in sheet.columns

    def test_sampling_is_deterministic(self, tmp_db):
        self.seed_predictions(n=20)
        a = sample_explanations(n=8, seed=7)["item_id"].tolist()
        b = sample_explanations(n=8, seed=7)["item_id"].tolist()
        assert a == b


class TestKrippendorffAlpha:
    def test_perfect_agreement_is_1(self):
        matrix = pd.DataFrame({"r1": [1, 3, 5], "r2": [1, 3, 5]})
        assert krippendorff_alpha(matrix, metric="interval") == 1.0

    def test_hand_computed_interval_case(self):
        # Items [1,2] and [4,5]: D_o = 1, D_e = 80/12 -> alpha = 1 - 12/80 = 0.85.
        matrix = pd.DataFrame({"r1": [1, 4], "r2": [2, 5]})
        assert krippendorff_alpha(matrix, metric="interval") == pytest.approx(0.85)

    def test_no_variation_is_1(self):
        matrix = pd.DataFrame({"r1": [3, 3], "r2": [3, 3]})
        assert krippendorff_alpha(matrix, metric="nominal") == 1.0

    def test_missing_ratings_handled(self):
        matrix = pd.DataFrame({"r1": [1, np.nan, 4], "r2": [1, 2, np.nan]})
        # Only item 1 is pairable and agrees -> alpha may be low/1 depending on
        # expected disagreement, but must not raise or return nan.
        alpha = krippendorff_alpha(matrix, metric="interval")
        assert not np.isnan(alpha)

    def test_all_singleton_units_gives_nan(self):
        matrix = pd.DataFrame({"r1": [1, 2], "r2": [np.nan, np.nan]})
        assert np.isnan(krippendorff_alpha(matrix))

    def test_systematic_disagreement_below_perfect(self):
        matrix = pd.DataFrame({"r1": [1, 1, 1, 5], "r2": [5, 5, 5, 1]})
        assert krippendorff_alpha(matrix, metric="interval") < 0


class TestRatingAnalysis:
    def make_sheets(self, directory):
        items = pd.DataFrame({"item_id": ["a", "b", "c"], "explanation_vi": ["x", "y", "z"]})
        for rater, scores in (("rater1", [4, 5, 3]), ("rater2", [4, 4, 3])):
            sheet = items.copy()
            sheet["accuracy_1_5"] = scores
            sheet["helpfulness_1_5"] = scores
            sheet["respectfulness_1_5"] = [5, 5, 5]
            sheet["comment"] = ""
            sheet.to_csv(directory / f"rating_sheet_{rater}.csv", index=False, encoding="utf-8-sig")

    def test_analyze_reports_means_and_alpha(self, tmp_path):
        self.make_sheets(tmp_path)
        results = analyze(tmp_path)
        assert results["n_raters"] == 2
        accuracy = results["criteria"]["accuracy_1_5"]
        assert accuracy["n_items_rated"] == 3
        assert accuracy["mean"] == pytest.approx(3.833, abs=0.001)
        assert accuracy["krippendorff_alpha"] is not None
        # Respectfulness has zero variance -> alpha 1.0.
        assert results["criteria"]["respectfulness_1_5"]["krippendorff_alpha"] == 1.0

    def test_out_of_range_scores_rejected(self, tmp_path):
        self.make_sheets(tmp_path)
        sheet = pd.read_csv(tmp_path / "rating_sheet_rater1.csv", encoding="utf-8-sig")
        sheet.loc[0, "accuracy_1_5"] = 7
        sheet.to_csv(tmp_path / "rating_sheet_rater1.csv", index=False, encoding="utf-8-sig")
        with pytest.raises(ValueError, match="outside 1-5"):
            load_sheets(tmp_path)

    def test_no_sheets_is_clear_error(self, tmp_path):
        with pytest.raises(SystemExit):
            load_sheets(tmp_path)


class TestSusScore:
    def test_standard_scoring_formula(self):
        # All 5s: odd items contribute 4 each, even items 0 -> 20 * 2.5 = 50.
        assert sus_score({f"q{i}": 5 for i in range(1, 11)}) == 50.0
        # Best possible: odd 5, even 1 -> 40 * 2.5 = 100.
        best = {f"q{i}": (5 if i % 2 == 1 else 1) for i in range(1, 11)}
        assert sus_score(best) == 100.0
        # Worst possible: odd 1, even 5 -> 0.
        worst = {f"q{i}": (1 if i % 2 == 1 else 5) for i in range(1, 11)}
        assert sus_score(worst) == 0.0

    def test_out_of_range_rejected(self):
        answers = {f"q{i}": 3 for i in range(1, 11)}
        answers["q4"] = 6
        with pytest.raises(ValueError):
            sus_score(answers)

    def test_grade_bands(self):
        assert grade(90).startswith("A")
        assert grade(75).startswith("B")
        assert grade(68).startswith("C")
        assert grade(55).startswith("D")
        assert grade(30).startswith("F")

    def test_score_file(self, tmp_path):
        rows = [{"respondent_id": "p1", **{f"q{i}": 4 if i % 2 else 2 for i in range(1, 11)}}]
        path = tmp_path / "sus.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        df = score_file(str(path))
        # odd=4 -> 3 each (15); even=2 -> 3 each (15); total 30 * 2.5 = 75.
        assert df["sus"].iloc[0] == 75.0
