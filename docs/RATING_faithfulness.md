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
system gave, and the passages it was retrieved against. Fill in `human_verdict`
with exactly one of `supported`, `partial` or `unsupported`, and leave everything
else as it is.

Edit it in VS Code or any plain-text editor. If you use Excel, import it through
**Data → From Text/CSV** with UTF-8 encoding and save it back as CSV UTF-8,
otherwise the dashes in the passages are garbled.

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
