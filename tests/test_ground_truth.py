"""Unit tests for the unified ground-truth label derivation."""

import pytest

from app.scoring import derive_ground_truth


class TestDeriveGroundTruth:
    @pytest.mark.parametrize(
        "dass,expected",
        [("Normal", "Low"), ("Mild", "Moderate"), ("Moderate", "Moderate"),
         ("Severe", "High"), ("Extremely Severe", "Severe")],
    )
    def test_dass_only(self, dass, expected):
        assert derive_ground_truth(dass_stress_severity=dass) == expected

    @pytest.mark.parametrize(
        "pss,expected",
        [("Low", "Low"), ("Moderate", "Moderate"), ("High", "High")],
    )
    def test_pss_only(self, pss, expected):
        assert derive_ground_truth(pss_category=pss) == expected

    def test_takes_more_severe_of_the_two(self):
        assert derive_ground_truth("Normal", "High") == "High"
        assert derive_ground_truth("Extremely Severe", "Low") == "Severe"
        assert derive_ground_truth("Mild", "Low") == "Moderate"

    def test_requires_at_least_one_input(self):
        with pytest.raises(ValueError):
            derive_ground_truth()

    def test_unknown_labels_rejected(self):
        with pytest.raises(ValueError):
            derive_ground_truth(dass_stress_severity="Bad")
        with pytest.raises(ValueError):
            derive_ground_truth(pss_category="Bad")
