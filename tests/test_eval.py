"""Tests for the synthetic generator and evaluation metrics."""

import random

from app.eval.evaluate import compute_metrics, load_label_pairs
from app.eval.synthetic import generate_student, seed_database, simulate_llm_prediction


class TestSyntheticGenerator:
    def test_generated_student_is_internally_consistent(self):
        rng = random.Random(1)
        record = generate_student(rng)
        assert set(record["dass_answers"].keys()) == set(range(1, 22))
        assert all(0 <= v <= 3 for v in record["dass_answers"].values())
        assert set(record["pss_answers"].keys()) == set(range(1, 11))
        assert all(0 <= v <= 4 for v in record["pss_answers"].values())
        assert record["ground_truth"] in ("Low", "Moderate", "High", "Severe")

    def test_high_theta_yields_high_stress(self):
        # With theta forced high, ground truth should skew severe.
        rng = random.Random(2)
        labels = []
        for _ in range(30):
            record = generate_student(rng)
            if record["theta"] > 0.75:
                labels.append(record["ground_truth"])
        assert labels, "expected some high-theta samples"
        assert all(lb in ("High", "Severe") for lb in labels)

    def test_simulated_prediction_agreement(self):
        rng = random.Random(3)
        agree = sum(
            simulate_llm_prediction(rng, "Moderate", 0.7)[0] == "Moderate" for _ in range(500)
        )
        assert 300 <= agree <= 400  # ~70% of 500

    def test_seed_database_writes_rows(self, tmp_db):
        count = seed_database(rows=25, seed=7)
        assert count == 25
        y_true, y_pred = load_label_pairs()
        assert len(y_true) == 25
        assert len(y_pred) == 25


class TestMetrics:
    def test_perfect_agreement(self):
        labels = ["Low", "Moderate", "High", "Severe"] * 5
        metrics = compute_metrics(labels, labels)
        assert metrics["accuracy"] == 1.0
        assert metrics["macro_f1"] == 1.0
        assert metrics["cohen_kappa"] == 1.0

    def test_metrics_shape(self):
        y_true = ["Low", "Low", "Moderate", "High", "Severe", "Moderate"]
        y_pred = ["Low", "Moderate", "Moderate", "High", "High", "Moderate"]
        metrics = compute_metrics(y_true, y_pred)
        assert 0 < metrics["accuracy"] < 1
        assert len(metrics["confusion_matrix"]) == 4
        assert metrics["n_samples"] == 6
        assert "Low" in metrics["per_class"]
