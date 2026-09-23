# Archive — superseded report artefacts

**Nothing in this folder is current.** It is kept so the history of the write-up
stays inspectable, not because any of it should be read for results.

The report that was submitted is [`report/latex/`](../latex/) (`main.tex` plus
`chapters/*.tex`). Build it with `build.ps1`. The authoritative numbers are in
[`docs/RESULTS.md`](../../docs/RESULTS.md) and `data/eval/`.

## What is here

| File | What it was | Why it is archived |
|---|---|---|
| `PreThesis_Report.md` | The report as a single Markdown file — the source of truth before the school template was adopted | Replaced by `report/latex/`. Rewriting it in the template was the point; keeping two report sources invites them to disagree, and they did. |
| `PreThesis_Report.tex` | LaTeX generated from that Markdown by `build_latex.py`, in a layout of my own | Superseded by the HCMIU template |
| `PreThesis_Report.docx` | Word generated from the same Markdown by `build_docx.py` | Same |
| `build_latex.py`, `build_docx.py` | The generators that read `PreThesis_Report.md` | Only useful for the archived Markdown |
| `*.bak` | An earlier slide deck and its builder | Point-in-time backups |

## Two specific errors in `PreThesis_Report.md`

Do not lift text or figures from it. Beyond being out of date in general, two
passages are wrong about how the deployed system behaves:

- **§4.7 quotes the old crisis-rule numbers** (precision 0.800 / recall 0.500).
  The rule was rebuilt around six suicide-risk constructs and re-measured on a
  held-out set frozen before the rewrite: precision 1.000, recall 0.867,
  F1 0.929.
- **§5.5 says free text is stored before the crisis rule runs.** It is not.
  Nothing is persisted and no external call is made until the crisis gate
  clears.

It also predates the 2026-09-19 discovery that 85 stub entries had contaminated
the evaluation cache, so every LLM figure in it is a contaminated one. See
`docs/RESULTS.md` for what replaced them.

## Note on `CITATIONS_TO_VERIFY.md`

[That file](../CITATIONS_TO_VERIFY.md) is still current and still worth reading
— the verification it records was done properly and the corrections it lists
were applied to `report/latex/bibliography.bib`. Its section references point
into `PreThesis_Report.md`, which now lives here.
