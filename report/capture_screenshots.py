"""Capture the five UI screenshots used in Chapter 6 of the LaTeX report.

Drives the running Streamlit app with Playwright. Navigation always goes through
in-app links, never through URLs: loading a URL starts a new Streamlit session
and would drop the answers already given.

Prerequisites (two terminals):
    uvicorn app.api.main:app --port 8000        # use a scratch DATABASE_URL
    streamlit run streamlit_app/Home.py --server.port 8501
Usage:
    python report/capture_screenshots.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

APP = "http://127.0.0.1:8501/"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "International_University__HCMIU___VNU__Pre_thesis_and_Thesis_LaTeX_Template__1_" / "images"

JOURNAL_TEXT = (
    "This week I felt overwhelmed. I have three deadlines on Friday and a midterm next "
    "week, so I have only been sleeping four or five hours a night. I keep worrying that "
    "I will fail the course and disappoint my parents, and I have stopped going to the gym."
)
CRISIS_TEXT = "I don't want to live anymore. Everything feels pointless."

# DASS-21: stress items high, anxiety and depression mild; items 17 and 21 stay at 1
# so the crisis rule does not fire on the normal path.
STRESS, ANXIETY = {1, 6, 8, 11, 12, 14, 18}, {2, 4, 7, 9, 15, 19, 20}
DASS = {i: 2 if i in STRESS else 1 for i in range(1, 22)}
# PSS-10: high perceived stress (reverse-scored items answered low).
PSS = {i: 1 if i in {4, 5, 7, 8} else 3 for i in range(1, 11)}


def settle(page: Page, ms: int = 700) -> None:
    """Wait for Streamlit to finish its rerun."""
    page.wait_for_timeout(ms)
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="hidden", timeout=15000)
    except Exception:
        pass


def scroll_top(page: Page) -> None:
    page.evaluate(
        "() => { const m = document.querySelector('[data-testid=\"stMain\"]') "
        "|| document.querySelector('section.main'); if (m) m.scrollTo(0, 0); window.scrollTo(0, 0); }"
    )
    page.wait_for_timeout(400)


def click_link(page: Page, text: str, sidebar: bool = False) -> None:
    scope = page.locator('[data-testid="stSidebar"]') if sidebar else page.locator('[data-testid="stMain"]')
    # :visible matters: the app hides Streamlit's built-in page nav with CSS, but
    # its <a> elements (with the same labels, e.g. "Results") stay in the DOM.
    scope.locator("a:visible", has_text=text).first.click()
    settle(page, 1500)


def consent(page: Page, shot: Path | None = None) -> None:
    page.goto(APP)
    page.get_by_text("Consent to take part").first.wait_for(timeout=60000)
    settle(page)
    page.locator("label", has_text="I have read and").first.click()
    settle(page)
    if shot:
        page.get_by_text("Consent to take part").first.evaluate("e => e.scrollIntoView({block: 'start'})")
        page.wait_for_timeout(500)
        page.screenshot(path=str(shot))
        print("  wrote", shot.name)
    page.get_by_role("button", name="Start the journey").click()
    page.locator("a", has_text="Continue: Share how you feel").first.wait_for(timeout=30000)
    click_link(page, "Continue: Share how you feel")


def write_journal(page: Page, text: str) -> None:
    box = page.locator("textarea").first
    box.wait_for(timeout=30000)
    box.fill(text)
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Saved.").first.wait_for(timeout=30000)


def answer(page: Page, answers: dict[int, int], upto: int | None = None) -> None:
    groups = page.locator('[role="radiogroup"]')
    groups.first.wait_for(timeout=30000)
    for qid, value in answers.items():
        if upto is not None and qid > upto:
            break
        groups.nth(qid - 1).locator("label").nth(value).click()
        settle(page, 250)


def analyse(page: Page, wait_text: str) -> None:
    page.get_by_role("button", name="Analyse now").click()
    page.get_by_text(wait_text).first.wait_for(timeout=300000)
    settle(page, 4000)  # let the Plotly charts draw


def normal_journey(browser) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1.5)
    consent(page, OUT / "screenshot_consent.png")
    write_journal(page, JOURNAL_TEXT)
    click_link(page, "Continue: DASS-21 questionnaire")

    answer(page, DASS, upto=12)
    scroll_top(page)
    page.screenshot(path=str(OUT / "screenshot_dass21.png"))
    print("  wrote screenshot_dass21.png")
    answer(page, {k: v for k, v in DASS.items() if k > 12})
    click_link(page, "Continue: PSS-10 questionnaire")

    answer(page, PSS)
    click_link(page, "Continue: Academic context")
    click_link(page, "Results", sidebar=True)

    analyse(page, "This level comes from your DASS-21 / PSS-10 scores")
    has_ai = page.get_by_text("The AI explanation is unavailable").count() == 0
    print("  AI explanation present:", has_ai)
    page.set_viewport_size({"width": 1280, "height": 1500})
    scroll_top(page)
    page.screenshot(path=str(OUT / "screenshot_results.png"))
    print("  wrote screenshot_results.png")

    click_link(page, "See your assessment history")
    page.get_by_text("Your journey").first.wait_for(timeout=60000)
    settle(page, 4000)
    page.set_viewport_size({"width": 1280, "height": 1300})
    scroll_top(page)
    page.screenshot(path=str(OUT / "screenshot_history.png"))
    print("  wrote screenshot_history.png")
    page.close()


def crisis_journey(browser) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=1.5)
    consent(page)
    write_journal(page, CRISIS_TEXT)
    click_link(page, "Results", sidebar=True)
    analyse(page, "You are not alone")
    scroll_top(page)
    page.screenshot(path=str(OUT / "screenshot_crisis.png"))
    print("  wrote screenshot_crisis.png")
    page.close()


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for journey in (crisis_journey, normal_journey):
            try:
                journey(browser)
            except Exception as exc:
                debug = OUT.parent.parent / f"_debug_{journey.__name__}.png"
                for pg in browser.contexts[-1].pages if browser.contexts else []:
                    pg.screenshot(path=str(debug))
                print(f"FAILED {journey.__name__}: {str(exc).splitlines()[0][:300]}  (debug: {debug})")
                sys.exit(1)
        browser.close()


if __name__ == "__main__":
    main()
