"""Build a local, self-contained page for rating the faithfulness sheet by hand.

Rating 30 rows in a CSV cell by cell - each with up to four passages of several
hundred words - is slow and error-prone. This writes one HTML file that shows a
row at a time with the judge's rubric beside it, takes a verdict with a click or
the keys 1 / 2 / 3, keeps progress in the browser, and downloads the filled
sheet in exactly the format `python -m app.eval.faithfulness_eval --agreement`
reads.

It reads ONLY the blind sheet. It refuses any file carrying a judge's verdict,
so pointing it at the key or at faithfulness_judgments.csv cannot leak the
answers into the page. The rubric is taken from the judge's own system prompt
rather than retyped, so the two cannot drift apart.

Usage:
    python scripts/make_rating_page.py            # -> data/eval/faithfulness_rating.html
    start data/eval/faithfulness_rating.html      # open it (Windows)

When done, move the downloaded file over data/eval/faithfulness_rating_sheet.csv.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.eval.faithfulness_eval import JUDGE_SYSTEM, OUT_DIR, RATING_SHEET  # noqa: E402

SHEET_COLUMNS = ["row_id", "suggestion", "passages", "human_verdict", "note"]
# Any of these would put an answer in front of the rater.
FORBIDDEN_COLUMNS = {"verdict", "evidence", "reason", "second_rater_verdict", "seen_before"}


def rubric_lines() -> list[str]:
    """The three verdict definitions and the closing instruction, verbatim from the judge."""
    lines = [ln.strip() for ln in JUDGE_SYSTEM.splitlines()]
    picked = [ln for ln in lines if ln.startswith(('- "supported"', '- "partial"', '- "unsupported"'))]
    picked += [ln for ln in lines if ln.startswith("Judge only against the passages")]
    if len(picked) != 4:
        raise RuntimeError("could not find the rubric in JUDGE_SYSTEM; it has changed shape")
    return picked


def build(sheet: Path, out: Path) -> Path:
    raw = sheet.read_bytes()
    frame = pd.read_csv(sheet, encoding="utf-8", dtype=str, keep_default_na=False)
    leaked = FORBIDDEN_COLUMNS & set(frame.columns)
    if leaked:
        raise SystemExit(f"{sheet.name} carries {sorted(leaked)} - that would show the rater the answers. "
                         "Point this at the blind rating sheet.")
    missing = [c for c in ("row_id", "suggestion", "passages") if c not in frame.columns]
    if missing:
        raise SystemExit(f"{sheet.name} is not a rating sheet: missing {missing}")

    rows = [
        {
            "row_id": r["row_id"],
            "suggestion": r["suggestion"],
            "passages": r["passages"],
            "human_verdict": r.get("human_verdict", "").strip().lower(),
            "note": "" if r.get("note", "") == "supported | partial | unsupported" else r.get("note", ""),
        }
        for r in frame.to_dict("records")
    ]
    payload = {
        "rows": rows,
        "rubric": rubric_lines(),
        "sheet_hash": hashlib.sha256(raw).hexdigest()[:16],
        "sheet_name": sheet.name,
    }
    # Escape "<" so no text in the data can close the script element.
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    out.write_text(PAGE.replace("__DATA__", data), encoding="utf-8")
    return out


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Faithfulness Rating</title>
<style>
  :root {
    --bg: #f7f6f2; --panel: #ffffff; --ink: #1c1c1e; --muted: #66666d; --line: #e3e0d8;
    --accent: #2f5d8a; --sup: #2e7d4f; --par: #a86b12; --uns: #b3261e; --chip: #efece5;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #141416; --panel: #1d1d21; --ink: #ececef; --muted: #9c9ca5; --line: #2d2d33;
      --accent: #8fb6e0; --sup: #6fcf97; --par: #f2c94c; --uns: #ff8a80; --chip: #26262b;
    }
  }
  :root[data-theme="dark"] {
    --bg: #141416; --panel: #1d1d21; --ink: #ececef; --muted: #9c9ca5; --line: #2d2d33;
    --accent: #8fb6e0; --sup: #6fcf97; --par: #f2c94c; --uns: #ff8a80; --chip: #26262b;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { position: sticky; top: 0; z-index: 2; background: var(--bg);
           border-bottom: 1px solid var(--line); padding: 10px 16px; }
  .bar { display: flex; gap: 16px; align-items: baseline; flex-wrap: wrap; }
  .bar h1 { font-size: 17px; margin: 0; }
  .bar .meta { color: var(--muted); font-size: 14px; }
  .progress { height: 4px; background: var(--line); border-radius: 2px; margin-top: 8px; overflow: hidden; }
  .progress > div { height: 100%; width: 0; background: var(--accent); transition: width .2s; }
  main { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 20px;
         padding: 16px; max-width: 1400px; margin: 0 auto; }
  @media (max-width: 860px) { main { grid-template-columns: minmax(0, 1fr); } }
  .left { position: sticky; top: 76px; align-self: start; display: grid; gap: 14px;
          max-height: calc(100vh - 92px); overflow-y: auto; padding-right: 4px; }
  @media (max-width: 860px) { .left { position: static; max-height: none; overflow: visible; } }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
  .label { font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin: 0 0 6px; }
  .suggestion { font-size: 18px; line-height: 1.5; margin: 0; }
  .choices { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .choice { font: inherit; font-size: 15px; padding: 8px 4px; border-radius: 8px; cursor: pointer;
            background: transparent; color: var(--c); border: 1.5px solid var(--c);
            display: flex; flex-direction: column; align-items: center; gap: 1px; min-width: 0; }
  .choice kbd { font: 11px ui-monospace, monospace; opacity: .75; }
  .choice[aria-pressed="true"] { background: var(--c); color: var(--panel); }
  .choice:focus-visible, .nav button:focus-visible, textarea:focus-visible, summary:focus-visible
    { outline: 2px solid var(--accent); outline-offset: 2px; }
  .sup { --c: var(--sup); } .par { --c: var(--par); } .uns { --c: var(--uns); }
  textarea { width: 100%; min-height: 54px; resize: vertical; font: inherit; font-size: 14px;
             background: var(--bg); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
  .nav { display: flex; gap: 8px; flex-wrap: wrap; }
  .nav button { font: inherit; font-size: 14px; padding: 7px 12px; border-radius: 8px; cursor: pointer;
                background: var(--chip); color: var(--ink); border: 1px solid var(--line); }
  .nav button.primary { background: var(--accent); color: var(--panel); border-color: var(--accent); }
  details summary { cursor: pointer; font-weight: 600; }
  .rubric p { margin: 8px 0; font-size: 14px; }
  .rubric p:last-child { font-weight: 600; }
  .hint { font-size: 13px; color: var(--muted); margin: 0; }
  .passage { margin-bottom: 12px; }
  .passage .pid { font: 12px ui-monospace, monospace; color: var(--muted); }
  .passage h3 { font-size: 15px; margin: 2px 0 8px; }
  .passage .doc { font-size: 12px; color: var(--muted); margin: 0 0 6px; }
  .passage .body { white-space: pre-wrap; font-size: 15px; margin: 0; }
  .toast { position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); background: var(--ink);
           color: var(--bg); padding: 6px 14px; border-radius: 18px; font-size: 14px; opacity: 0; transition: opacity .2s; }
  .toast.show { opacity: .92; }
  .dots { display: flex; flex-wrap: wrap; gap: 4px; }
  .dot { width: 22px; height: 22px; border-radius: 5px; border: 1px solid var(--line); background: var(--chip);
         font-size: 11px; display: grid; place-items: center; cursor: pointer; color: var(--muted); }
  .dot.done { background: var(--accent); color: var(--panel); border-color: var(--accent); }
  .dot.here { outline: 2px solid var(--ink); outline-offset: 1px; }
</style>
</head>
<body>
<header>
  <div class="bar">
    <h1>Faithfulness rating</h1>
    <span class="meta" id="where"></span>
    <span class="meta" id="count"></span>
  </div>
  <div class="progress"><div id="progress"></div></div>
</header>
<main>
  <section class="left">
    <details class="card rubric" id="rubric-box">
      <summary>Rubric — the judge's own instruction, verbatim</summary>
      <div id="rubric"></div>
    </details>
    <div class="card">
      <p class="label">Suggestion</p>
      <p class="suggestion" id="suggestion"></p>
    </div>
    <div class="card">
      <p class="label">Your verdict</p>
      <div class="choices">
        <button class="choice sup" data-v="supported" aria-pressed="false"><kbd>1</kbd>Supported</button>
        <button class="choice par" data-v="partial" aria-pressed="false"><kbd>2</kbd>Partial</button>
        <button class="choice uns" data-v="unsupported" aria-pressed="false"><kbd>3</kbd>Unsupported</button>
      </div>
      <p class="label" style="margin-top:12px">Note (optional)</p>
      <textarea id="note" placeholder="Anything worth recording about this row"></textarea>
    </div>
    <div class="nav">
      <button id="prev">← Prev</button>
      <button id="next">Next →</button>
      <button id="unrated">Next unrated</button>
      <button id="clear">Clear verdict</button>
      <button id="download" class="primary">Download CSV</button>
    </div>
    <div class="dots" id="dots" aria-label="Rows"></div>
    <p class="hint">Keys: <b>1</b>/<b>2</b>/<b>3</b> rate and move on, <b>←</b>/<b>→</b> move. Progress is kept in this
      browser. When done, download and move the file over <code>data/eval/</code><span id="sheetname"></span>.</p>
  </section>
  <section id="passages"></section>
</main>
<div class="toast" id="toast" role="status"></div>
<script type="application/json" id="data">__DATA__</script>
<script>
(function () {
  const DATA = JSON.parse(document.getElementById("data").textContent);
  const rows = DATA.rows;
  const KEY = "faithfulness-rating-" + DATA.sheet_hash;
  const VALID = ["supported", "partial", "unsupported"];
  let state = rows.map(r => ({ verdict: VALID.includes(r.human_verdict) ? r.human_verdict : "", note: r.note || "" }));
  let at = 0;

  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (saved && Array.isArray(saved.state) && saved.state.length === rows.length) {
      state = saved.state; at = Math.min(saved.at || 0, rows.length - 1);
    }
  } catch (e) { /* storage unavailable: work in memory */ }
  const persist = () => { try { localStorage.setItem(KEY, JSON.stringify({ state, at })); } catch (e) {} };

  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const bold = s => esc(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  $("rubric").innerHTML = DATA.rubric.map(l => "<p>" + esc(l.replace(/^- /, "")) + "</p>").join("");
  $("sheetname").textContent = DATA.sheet_name;
  try { if (!localStorage.getItem(KEY)) $("rubric-box").open = true; } catch (e) { $("rubric-box").open = true; }

  function parsePassages(s) {
    const re = /^\[([^\]\n]+?\.md::\d+)\] ([^\n]*)$/gm;
    const marks = [...s.matchAll(re)];
    if (!marks.length) return [{ id: "", heading: "Passages", doc: "", body: s }];
    return marks.map((m, i) => {
      const end = i + 1 < marks.length ? marks[i + 1].index : s.length;
      let lines = s.slice(m.index + m[0].length, end).trim().split("\n");
      const doc = lines.length ? lines.shift() : "";
      lines = lines.filter(l => l.trim() !== "## " + m[2].trim());
      return { id: m[1], heading: m[2], doc: doc, body: lines.join("\n").trim() };
    });
  }

  const dots = $("dots");
  rows.forEach((r, i) => {
    const d = document.createElement("button");
    d.className = "dot"; d.textContent = r.row_id; d.title = "Row " + r.row_id;
    d.addEventListener("click", () => go(i)); dots.appendChild(d);
  });

  function render() {
    const r = rows[at], s = state[at];
    $("suggestion").textContent = r.suggestion;
    $("note").value = s.note;
    document.querySelectorAll(".choice").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === s.verdict)));
    $("passages").innerHTML = parsePassages(r.passages).map(p =>
      '<article class="card passage"><div class="pid">' + esc(p.id) + '</div><h3>' + esc(p.heading) +
      '</h3>' + (p.doc ? '<p class="doc">' + esc(p.doc) + '</p>' : '') +
      '<p class="body">' + bold(p.body) + '</p></article>').join("");
    const done = state.filter(x => x.verdict).length;
    $("where").textContent = "Row " + r.row_id + " (" + (at + 1) + " of " + rows.length + ")";
    $("count").textContent = done + " rated";
    $("progress").style.width = (100 * done / rows.length) + "%";
    [...dots.children].forEach((d, i) => { d.classList.toggle("done", !!state[i].verdict); d.classList.toggle("here", i === at); });
    window.scrollTo({ top: 0 });
  }
  function go(i) { at = Math.max(0, Math.min(rows.length - 1, i)); persist(); render(); }
  function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove("show"), 1100); }
  function rate(v) {
    state[at].verdict = v; persist();
    toast("Row " + rows[at].row_id + ": " + v);
    if (at < rows.length - 1) go(at + 1); else render();
  }

  document.querySelectorAll(".choice").forEach(b => b.addEventListener("click", () => rate(b.dataset.v)));
  $("note").addEventListener("input", e => { state[at].note = e.target.value; persist(); });
  $("prev").addEventListener("click", () => go(at - 1));
  $("next").addEventListener("click", () => go(at + 1));
  $("unrated").addEventListener("click", () => {
    const i = state.findIndex((x, j) => !x.verdict && j > at);
    const k = i >= 0 ? i : state.findIndex(x => !x.verdict);
    if (k >= 0) go(k); else toast("Every row is rated");
  });
  $("clear").addEventListener("click", () => { state[at].verdict = ""; persist(); render(); });
  document.addEventListener("keydown", e => {
    if (e.target.tagName === "TEXTAREA" || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "1") rate("supported");
    else if (e.key === "2") rate("partial");
    else if (e.key === "3") rate("unsupported");
    else if (e.key === "ArrowLeft") go(at - 1);
    else if (e.key === "ArrowRight") go(at + 1);
  });

  $("download").addEventListener("click", () => {
    const done = state.filter(x => x.verdict).length;
    if (done < rows.length &&
        !confirm(done + " of " + rows.length + " rows are rated. Download anyway? Unrated rows are ignored by --agreement."))
      return;
    const q = v => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
    const header = ["row_id", "suggestion", "passages", "human_verdict", "note"];
    const lines = [header.join(",")].concat(rows.map((r, i) =>
      [r.row_id, r.suggestion, r.passages, state[i].verdict, state[i].note].map(q).join(",")));
    const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = DATA.sheet_name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  render();
})();
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sheet", type=Path, default=RATING_SHEET)
    parser.add_argument("--out", type=Path, default=OUT_DIR / "faithfulness_rating.html")
    args = parser.parse_args()
    out = build(args.sheet, args.out)
    print(f"Wrote {out}. Open it in a browser; when done, move the download over {args.sheet}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
