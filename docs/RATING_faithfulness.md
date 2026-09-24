# Rating sheet — faithfulness of generated suggestions

This is the human validation of the faithfulness judge (`qwen/qwen3.8-27b`). Until
it is done, "75 % of suggestions fully supported" is one model's opinion. It takes
one to two hours.

## Before you start: what not to open

Opening any of these before you finish would anchor your ratings on someone else's:

- `data/eval/faithfulness_rating_key.csv` — the judge's verdict for each row
- `data/eval/faithfulness_judgments.csv` — every verdict, with the judge's reasons
- `data/eval/faithfulness_second_rater*.csv` — a second model's ratings of an
  earlier sheet

Also skip the **"Judge validation"** paragraph of `docs/RESULTS.md` §4b until you
are done.

## The sheet

`data/eval/faithfulness_rating_sheet.csv` — 30 rows. Each has a suggestion the
system gave, and the passages it was retrieved against.

**The easy way — a local rating page (about 30–40 minutes):**

```powershell
python scripts/make_rating_page.py
start data\eval\faithfulness_rating.html
```

One row at a time, the rubric beside it, keys **1 / 2 / 3** to rate and move on,
**← / →** to go back and forth. Progress is kept in the browser, so you can stop
and come back. When every row is rated, press **Download CSV**, then move the
download over the sheet:

```powershell
Move-Item "$HOME\Downloads\faithfulness_rating_sheet.csv" data\eval\faithfulness_rating_sheet.csv -Force
```

The page is built from the blind sheet only, and refuses any file that carries a
verdict, so it cannot show you the judge's answers.

**By hand instead:** fill `human_verdict` with exactly one of `supported`,
`partial` or `unsupported` and leave everything else as it is. Use VS Code or a
plain-text editor; in Excel, import through **Data → From Text/CSV** as UTF-8 and
save back as CSV UTF-8, or the dashes in the passages are garbled.

The rows were drawn at random within each of the judge's verdicts (seed 7), so the
rare verdicts are over-represented: do not expect the sheet to look like the
75 / 24 / 1 split of the full set.

Two of the 30 rows also appeared on an earlier sheet whose ratings were discussed
in the working session. They are the only two "unsupported" rows in the whole set,
so a sheet that covers that verdict cannot avoid them; the key marks them
`seen_before`. Rate them from the rubric, not from memory.

## The rubric

This is the judge's own instruction, verbatim. Apply it literally — the point is
to find out whether a person reading these words reaches the same verdicts.

> For EACH numbered suggestion, decide:
> - **"supported"**: the action it recommends, and every specific detail it gives
>   (technique, number, service, phone number, time), is stated in or directly
>   implied by at least one passage. Rephrasing and addressing the reader
>   personally are fine.
> - **"partial"**: the core action appears in a passage, but the suggestion adds at
>   least one specific detail that no passage contains.
> - **"unsupported"**: the core action does not appear in any passage.
>
> Judge only against the passages. Do not use your own knowledge of what is good
> advice.

The last line is the hard one. A suggestion can be excellent advice and still be
`unsupported` if the passages shown do not contain it.

## When you are done

```powershell
python -m app.eval.faithfulness_eval --agreement
```

It reports raw agreement and Cohen's kappa between you and the judge. **Quote
kappa, not raw agreement** — the sheet is deliberately enriched for disagreement,
so raw agreement understates the full set.

Then commit the filled sheet: it is the human validation, and it belongs in the
record next to the judge's verdicts.
