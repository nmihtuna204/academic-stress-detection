"""Every place that shows a stress level must follow the same rule as the Results hero.

The questionnaire is authoritative whenever one was completed. The History page
and both trend charts once led with the language model's label instead, in four
separately written copies of the rule, so one assessment read "High" on Results
and "Very high" in History. Found by recording the README demo.
"""

import importlib.util
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "streamlit_app"
sys.path.insert(0, str(APP_DIR))
_spec = importlib.util.spec_from_file_location("streamlit_app_utils", APP_DIR / "utils.py")
ui_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui_utils)


def test_the_questionnaire_decides_when_there_is_one():
    record = {"ground_truth_label": "High", "llm_predicted_label": "Severe"}
    assert ui_utils.headline_level(record) == "High"


def test_the_model_stands_in_only_without_a_questionnaire():
    assert ui_utils.headline_level({"ground_truth_label": None, "llm_predicted_label": "Moderate"}) == "Moderate"
    assert ui_utils.headline_level({"llm_predicted_label": "Low"}) == "Low"


def test_nothing_to_show_is_none():
    assert ui_utils.headline_level({"ground_truth_label": None, "llm_predicted_label": None}) is None


def test_no_page_restates_the_rule_model_first():
    model_first = re.compile(r"""llm_predicted_label["']\]?\)?\s+or\b""")
    offenders = [
        f"{path.relative_to(APP_DIR)}:{n}"
        for path in APP_DIR.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if model_first.search(line)
    ]
    assert not offenders, f"model label put ahead of the questionnaire: {offenders}; use headline_level()"
