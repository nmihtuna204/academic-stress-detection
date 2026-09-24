"""The local rating page must carry the sheet, the judge's rubric, and nothing that reveals an answer."""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import make_rating_page as mrp  # noqa: E402


def _sheet(tmp_path, suggestion="Sleep 7-8 hours.", extra: dict | None = None):
    row = {"row_id": 1, "suggestion": suggestion,
           "passages": "[04.md::0] Sleep\nSleep, exams\n\n## Sleep\n\nSleep 7-8 hours.",
           "human_verdict": "", "note": "supported | partial | unsupported"}
    row.update(extra or {})
    path = tmp_path / "faithfulness_rating_sheet.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    return path


def _payload(html: str) -> dict:
    block = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
    return json.loads(block)


def test_page_carries_the_rows_and_the_judges_rubric(tmp_path):
    out = mrp.build(_sheet(tmp_path), tmp_path / "page.html")
    data = _payload(out.read_text(encoding="utf-8"))
    assert data["rows"][0]["suggestion"] == "Sleep 7-8 hours."
    assert data["rows"][0]["note"] == "", "the column hint is not a note"
    assert data["rubric"][0].startswith('- "supported"')
    assert len(data["rubric"]) == 4


def test_text_in_the_data_cannot_close_the_script_element(tmp_path):
    out = mrp.build(_sheet(tmp_path, suggestion="x</script><img src=x onerror=alert(1)>"), tmp_path / "p.html")
    html = out.read_text(encoding="utf-8")
    assert html.count("</script>") == 2, "only the page's own two script elements may close"
    assert _payload(html)["rows"][0]["suggestion"].startswith("x</script>")


@pytest.mark.parametrize("column", ["verdict", "seen_before", "second_rater_verdict"])
def test_a_file_that_carries_answers_is_refused(tmp_path, column):
    with pytest.raises(SystemExit, match=column):
        mrp.build(_sheet(tmp_path, extra={column: "supported"}), tmp_path / "p.html")


def test_rubric_is_read_from_the_judge_not_retyped():
    from app.eval.faithfulness_eval import JUDGE_SYSTEM

    for line in mrp.rubric_lines():
        assert line in JUDGE_SYSTEM
