"""Record the README demo: one walk through the app, as a captioned GIF.

Reuses the navigation in capture_screenshots.py, which is known to work against
this Streamlit app (in-app links only; a URL load starts a new session). Each
step is a still frame with a caption band, so the GIF stays sharp and small and
needs no video tooling.

Prerequisites (two terminals), ideally against a scratch database:
    $env:DATABASE_URL = "sqlite:///C:/temp/demo.db"
    uvicorn app.api.main:app --port 8000
    streamlit run streamlit_app/Home.py --server.port 8501
The normal journey makes one LLM call; the crisis journey makes none.

Usage:
    python report/record_demo.py      # -> docs/assets/demo.gif
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_screenshots import (  # noqa: E402
    CRISIS_TEXT,
    DASS,
    JOURNAL_TEXT,
    PSS,
    analyse,
    answer,
    click_link,
    consent,
    scroll_top,
    settle,
    write_journal,
)

ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"
VIEW = {"width": 1280, "height": 800}
GIF_WIDTH = 960


def _font(size: int):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grab(page: Page, caption: str, frames: list, hold_ms: int = 2600) -> Image.Image:
    path = ASSETS / "_frame.png"
    page.screenshot(path=str(path))
    shot = Image.open(path).convert("RGB")
    band = 46
    framed = Image.new("RGB", (shot.width, shot.height + band), (28, 28, 30))
    framed.paste(shot, (0, 0))
    ImageDraw.Draw(framed).text((20, shot.height + 11), caption, fill=(236, 236, 239), font=_font(20))
    frames.append((framed, hold_ms))
    path.unlink()
    print("  frame:", caption)
    return shot


def scroll_to(page: Page, text: str) -> bool:
    target = page.get_by_text(text).first
    if target.count() == 0:
        return False
    target.evaluate("e => e.scrollIntoView({block: 'start'})")
    page.wait_for_timeout(600)
    return True


def normal(browser, frames: list) -> None:
    page = browser.new_page(viewport=VIEW)
    page.goto("http://127.0.0.1:8501/")
    page.get_by_text("Consent to take part").first.wait_for(timeout=60000)
    settle(page)
    page.locator("label", has_text="I have read and").first.click()
    settle(page)
    grab(page, "1 · Informed consent: what is stored, for how long, and who processes it", frames)
    page.get_by_role("button", name="Start the journey").click()
    page.locator("a", has_text="Continue: Share how you feel").first.wait_for(timeout=30000)
    click_link(page, "Continue: Share how you feel")

    write_journal(page, JOURNAL_TEXT)
    scroll_top(page)
    grab(page, "2 · The student writes freely, in English or Vietnamese", frames)
    click_link(page, "Continue: DASS-21 questionnaire")

    answer(page, DASS, upto=8)
    scroll_top(page)
    grab(page, "3 · Validated instruments: DASS-21 and PSS-10", frames, 2000)
    answer(page, {k: v for k, v in DASS.items() if k > 8})
    click_link(page, "Continue: PSS-10 questionnaire")
    answer(page, PSS)
    click_link(page, "Continue: Academic context")
    click_link(page, "Results", sidebar=True)

    analyse(page, "This level comes from your DASS-21 / PSS-10 scores")
    scroll_top(page)
    grab(page, "4 · The level comes from the validated instrument, not from the LLM", frames, 3200)
    if scroll_to(page, "Things you could try"):
        grab(page, "5 · Advice grounded in retrieved passages, with verified citations", frames, 3600)
    elif scroll_to(page, "unavailable"):
        grab(page, "5 · When nothing grounds the advice, the app says so instead of inventing it", frames, 3600)

    click_link(page, "See your assessment history")
    page.get_by_text("Your journey").first.wait_for(timeout=60000)
    settle(page, 3000)
    scroll_top(page)
    grab(page, "6 · History shows the same level as Results, and the AI's differing reading beside it", frames)
    if scroll_to(page, "Delete my data"):
        page.get_by_text("Yes, I want to permanently delete").first.click()
        settle(page)
        scroll_to(page, "Delete my data")
        grab(page, "7 · Two steps to erase everything stored under the anonymous code", frames, 2400)
    page.close()


def crisis(browser, frames: list) -> None:
    page = browser.new_page(viewport=VIEW)
    consent(page)
    write_journal(page, CRISIS_TEXT)
    click_link(page, "Results", sidebar=True)
    analyse(page, "You are not alone")
    scroll_top(page)
    grab(page, "8 · Self-harm risk: a deterministic gate shows helplines, before anything is stored", frames, 4000)
    page.close()


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    frames: list = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        normal(browser, frames)
        crisis(browser, frames)
        browser.close()

    scaled = []
    for img, _ms in frames:
        h = round(img.height * GIF_WIDTH / img.width)
        scaled.append(img.resize((GIF_WIDTH, h), Image.LANCZOS).quantize(colors=128, method=Image.MEDIANCUT))
    out = ASSETS / "demo.gif"
    scaled[0].save(out, save_all=True, append_images=scaled[1:], duration=[ms for _i, ms in frames],
                   loop=0, optimize=True)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(frames)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
