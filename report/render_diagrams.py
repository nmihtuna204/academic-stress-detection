r"""Render the Mermaid blocks in report/REPORT_DIAGRAMS.md to PNG files.

Each diagram section in the Markdown is headed `## N — diagram_xxx.png`; the
first ```mermaid block after that heading is rendered with Mermaid in headless
Chromium (Playwright) and saved under the LaTeX template's images/ folder, where
the report's \\diagram macro picks it up automatically.

Usage:
    python report/render_diagrams.py            # render all
    python report/render_diagrams.py er sequence  # only files whose name contains a filter
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "REPORT_DIAGRAMS.md"
OUT = ROOT / "latex" / "images"
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:0;background:#fff;font-family:'Segoe UI',Arial,sans-serif}
#out{display:inline-block;padding:16px}</style>
<script src="%s"></script></head><body><div id="out"></div></body></html>""" % MERMAID_JS

RENDER_JS = """async (src) => {
  mermaid.initialize({startOnLoad:false, securityLevel:'loose', theme:'default',
    // wrappingWidth: subgraph titles wrap at 200px by default and the second line
    // is hidden behind the nodes, so long titles such as "API layer — FastAPI +
    // Pydantic v2" were clipped.
    flowchart:{htmlLabels:true, useMaxWidth:false, wrappingWidth:600}, sequence:{useMaxWidth:false},
    er:{useMaxWidth:false}, fontFamily:"'Segoe UI', Arial, sans-serif"});
  const {svg} = await mermaid.render('d' + Date.now(), src);
  document.getElementById('out').innerHTML = svg;
  return true;
}"""


def extract() -> list[tuple[str, str]]:
    text = SOURCE.read_text(encoding="utf-8")
    items = []
    for m in re.finditer(r"^## \d+ — `(diagram_[a-z_]+\.png)`.*?^```mermaid\n(.*?)^```", text, re.S | re.M):
        items.append((m.group(1), m.group(2)))
    return items


def main(filters: list[str]) -> None:
    diagrams = [d for d in extract() if not filters or any(f in d[0] for f in filters)]
    print(f"{len(diagrams)} diagram(s) to render -> {OUT}")
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2.5, viewport={"width": 1600, "height": 1200})
        page.set_content(PAGE)
        page.wait_for_function("typeof mermaid !== 'undefined'", timeout=30000)
        for name, src in diagrams:
            try:
                page.evaluate(RENDER_JS, src)
                page.locator("#out").screenshot(path=str(OUT / name), omit_background=False)
                print(f"  ok    {name}")
            except Exception as exc:  # report every broken diagram, keep going
                failures += 1
                print(f"  FAIL  {name}: {str(exc).splitlines()[0][:200]}")
        browser.close()
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
