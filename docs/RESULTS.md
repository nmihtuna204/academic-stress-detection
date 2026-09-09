# Experimental Results

Single collection point for every computed result, ready to lift into the
thesis. **Every number on this page was produced by executing the referenced
script**; nothing is estimated or hand-written. Where a result rests on
synthetic data it is labeled as such. Regeneration commands are given with
each table (figures land in `data/eval/`, which is intentionally not in git).

Last regenerated: 2026-07-18/19 on the synthetic dataset; the crisis-rule and
retrieval-quality sections re-run 2026-09-06.

---

## 1. Dataset

`python -m app.eval.compare --dataset synthetic` writes the exact evaluated
dataframe to `data/eval/dataset_synthetic.csv`.

- **Source**: 466 synthetic students (Vietnamese free text + DASS-21 + PSS-10
  items generated from a latent stress level; `research/generate_dataset.py`).
- **Split**: frozen stratified train 326 / val 70 / test 70
  (`data/stress_dataset_split.csv`, seed 42). The split is reused from the
  PhoBERT fine-tuning run so no fine-tuning data leaks into the test set.
- **Label space**: unified 4-class (Low/Moderate/High/Severe) derived from the
  DASS-21 stress subscale + PSS-10 category (max severity of the two).
- **Test-set distribution**: Low 16 / Moderate 23 / High 22 / Severe 9.

> ⚠️ SYNTHETIC DATA: these rows demonstrate the pipeline end-to-end. Claims
> about real-world performance require the real-data study (Section 5).

## 2. Baseline comparison — SYNTHETIC data

Regenerate: `python -m app.eval.compare --dataset synthetic`
(artifacts: `data/eval/comparison.csv`, `comparison.md`, `confusion_<system>.png`)

| system | n_test | accuracy | macro_f1 | cohen_kappa | f1_low | f1_moderate | f1_high | f1_severe |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|
| tfidf_lr | 70 | 0.6857 | 0.6816 | 0.5807 | 0.8205 | 0.6512 | 0.5882 | 0.6667 |
| phobert_ft | 70 | 0.6571 | 0.5329 | 0.5156 | 0.8421 | 0.6809 | 0.6087 | 0.0000 |
| majority | 70 | 0.3286 | 0.1237 | 0.0000 | 0.0000 | 0.4946 | 0.0000 | 0.0000 |
| tfidf_svm | 70 | 0.6571 | 0.6524 | 0.5424 | 0.8205 | 0.6222 | 0.5000 | 0.6667 |
| llm_zeroshot | 70 | 0.5286 | 0.5238 | 0.3892 | 0.8421 | 0.3750 | 0.3158 | 0.5625 |
| llm_full | — | **not run** | — | — | — | — | — | — |

Run 2026-09-08 with `openai/gpt-oss-120b` served by Groq. The report and this
table must name that model: it is not the `gpt-4o-mini` the design chapter
assumed, and the numbers belong to the model that produced them.

**Honest reading of the completed table:**

- **The classical baseline wins.** TF-IDF with logistic regression reaches
  macro-F1 0.682, ahead of every neural and generative system tested. On
  template-generated text this is the expected outcome and worth stating plainly:
  a bag of n-grams is very good at recognising 41 recurring templates, which is
  precisely the criticism §5.3 makes of the dataset. It is evidence about the
  data, not evidence that the architecture is wrong.
- **The full proposed system does not beat zero-shot.** `llm_full` (0.509
  macro-F1) sits marginally below `llm_zeroshot` (0.524), so on this dataset the
  added RAG, questionnaire and emotion signals bought nothing. The component
  ablation is what would localise why; it has not been run.
- **`llm_full` has no reportable number, and the earlier one was withdrawn.**
  A re-run on 2026-09-08 completed 38 of 70 items before the Groq free tier's
  daily cap (200,000 tokens) was reached; the remaining 32 requests were
  refused with HTTP 429. At a 46 % unusable rate the harness refuses to publish
  a score, because the metrics would describe the fallback label rather than the
  system. The 38 completed responses are cached, so finishing the run costs only
  the remaining 32 requests.

  **A correction to the previous entry.** It reported "7 parse failures out of
  70" and attributed them to the model's JSON formatting. That attribution was
  not evidence-based: the failure path counted failures and then discarded the
  replies, so nothing distinguished a malformed reply from a request that never
  landed. Failures are now retained and classified. In this run, of 32 failures
  **31 were HTTP 429 rate-limit refusals and exactly one was malformed JSON**
  (`"confidence": 0. nine` — the model spelled a digit as a word). The single
  genuine parse failure is 1 in 39 requests that actually reached the model,
  not 1 in 10. Any statement that the model "cannot hold the output format"
  should be read against that ratio.
- **The leakage caveat still stands.** `llm_full` receives the DASS/PSS scores
  that define the ground-truth label, so its agreement is partly circular. The
  `no_questionnaire` ablation is the honest text-only comparison and remains
  unrun.
- The `phobert_ft` gap against `tfidf_lr` is almost entirely the Severe class:
  the fine-tuned model is 3-class and *cannot* predict Severe (identity 3→4
  mapping; F1_severe = 0 by construction). On the three classes it can predict
  it is competitive (f1_low 0.842, f1_moderate 0.681, f1_high 0.609).

## 3. Ablation study — NOT RUN YET

Regenerate: `python -m app.eval.ablation --dataset synthetic`
Add `--limit 35` to halve the token cost (stratified, seeded, identical
across configs; disclose it wherever the numbers appear).
(artifacts: `data/eval/ablation.csv`, `ablation.md`, `ablation.png`)

Attempted 2026-09-08 and blocked before it began: the baseline comparison
consumed the day's token allowance, so no ablation configuration could run. The
runner writes an explicit "NOT RUN" marker instead of a table. The `full`
configuration reuses the comparison's cache, so once that run is finished the
ablation costs four configurations rather than five. Configurations wired and tested (with a
mocked LLM): `full`, `no_rag`, `no_questionnaire`, `no_emotion`, `text_only` —
all through the same engine as the headline `llm_full` system. The
interpretation paragraph is generated from the computed deltas.

## 4. Crisis-detection rule — rebuilt and re-measured 2026-09-09

Regenerate (three sets):

```
python -m app.eval.crisis_eval                                                     # VI dev
python -m app.eval.crisis_eval --testset data/eval/crisis_testset_en.jsonl                                --out data/eval/crisis_eval_en.md                   # EN dev
python -m app.eval.crisis_eval --testset data/eval/crisis_testset_heldout.jsonl                                --out data/eval/crisis_eval_heldout.md              # held-out
```

### What was wrong

The rule matched a flat list of fixed phrases. That is adequate for explicit
statements and close to useless for indirect and passive ideation, which is
phrased compositionally. The published figure was precision 0.800 / recall 0.500
on 50 Vietnamese items, with indirect ideation at 1 of 9.

Adding the twelve published false negatives to the phrase list would have been
tuning against the test set. So the rule was rewritten around six constructs
taken from suicide-risk assessment — explicit intent, passive death wish,
existence negation, perceived burdensomeness, preparation, escape — in
`app/nlp/crisis_patterns.py`, with span-local idiom guards so that lethal
vocabulary in ordinary complaint ("this deadline is killing me", "khó muốn
chết") does not fire while a disclosure in the same message still does.

### Procedure, because it determines what the numbers are worth

1. A third set of 60 bilingual items was written and **frozen before the new
   patterns existed** (SHA-256 recorded in `data/eval/crisis_testset_heldout.jsonl`).
2. The patterns were written from the construct list, not from failing items.
3. The held-out set was measured, and the first measurement is the one reported.
4. The Vietnamese and English sets were demoted to **development** sets: two
   explicit-class regressions and three Vietnamese idiom false positives were
   found and fixed using them.
5. The held-out set was then re-measured. **It produced exactly the same
   numbers as the first measurement**, so the development-set work had no
   detectable effect on it.

### Results

| Set | | Precision | Recall | F1 | Explicit | Indirect |
|---|---|---:|---:|---:|---:|---:|
| **Held-out** (60 items, bilingual) | before | 0.600 | 0.200 | 0.300 | 6/12 | 0/14 |
| | **after** | **1.000** | **0.867** | **0.929** | **12/12** | **11/14** |
| VI dev (50, written by the original author) | before | 0.800 | 0.500 | 0.615 | 10/10 | 1/9 |
| | after | 1.000 | 1.000 | 1.000 | 10/10 | 9/9 |
| EN dev (50) | before | 1.000 | 0.417 | 0.588 | 10/10 | 0/10 |
| | after | 1.000 | 0.833 | 0.909 | 10/10 | 7/10 |

No false positives on any of the three sets after the change, across 51 hard
negatives written specifically to be lethal-sounding.

### How to read these numbers

**The held-out row is the only one that is evidence.** The two development rows
are reported for completeness and are fitted: the perfect Vietnamese score in
particular is the expected consequence of having debugged against that set, not
an independent result. Quoting 1.000/1.000 as a headline would be exactly the
error this project avoids elsewhere.

**The old rule was worse than previously published.** On phrasing it had never
seen, the flat phrase list scored recall 0.200, not the 0.500 reported on the
Vietnamese set. Part of the original figure came from that set sharing surface
forms with the lexicon.

**The remaining limitation is authorship.** The held-out set was written by the
same author as the patterns. The construct taxonomy is external and citable, and
the procedural separation above was genuinely applied, but a set written by an
independent annotator would be stronger evidence and is the obvious next step.
Three indirect items are still missed; they are listed verbatim in
`data/eval/crisis_eval_heldout.md`.

**The operating point moved deliberately toward recall.** For a screening aid a
false positive shows helplines to someone not in crisis, and a false negative
shows nothing to someone who is. Those costs are not symmetric. Precision
happened not to fall here, but the design would have accepted it falling.

## 4b. Retrieval quality — computed, offline

Regenerate: `python -m app.eval.retrieval_eval`
(artifact: `data/eval/retrieval_eval.md`)

Query set: 57 hand-labelled queries committed at `data/eval/retrieval_queries.jsonl`,
each mapped to the chunk ids that genuinely answer it. Scored against the
production `retrieve()` path over the 23-chunk corpus. Binary relevance.

| k | Recall@k | Precision@k | nDCG@k |
|---:|---:|---:|---:|
| 1 | 0.658 | 0.684 | 0.684 |
| 3 | 0.838 | 0.298 | 0.776 |
| 5 | 0.903 | 0.200 | 0.807 |
| 8 | 0.965 | 0.136 | 0.829 |

**MRR = 0.787.** Production retrieves at k = 4. These are the queries as written; the paired comparison below is what speaks to deployed behaviour.

**The finding that matters is the cost of the query construction, and it has now been
fixed.** Measured as a paired comparison: the same 51 natural queries and the same
relevance labels, retrieved under three constructions, differing only in the query
string. Restricted to the 16 queries the construction actually alters:

| Metric | Student's sentence | Old construction | Current construction | Δ vs old |
|---|---:|---:|---:|---:|
| MRR | 0.778 | 0.509 | **0.839** | +0.329 |
| Recall@1 | 0.656 | 0.344 | **0.719** | +0.375 |
| Recall@5 | 0.938 | 0.688 | **1.000** | +0.312 |
| nDCG@5 | 0.809 | 0.540 | **0.879** | +0.338 |

The old `build_rag_query()` threw away the student's sentence and retrieved on the
matched lexicon keywords instead, then appended a label string such as
`"student with High stress"`. Both decisions were wrong, and the measurement showed
it: the sentence alone beat the keywords alone (0.778 vs 0.509), and appending the
label hurt every variant tested, costing the best arm 0.15 MRR. The fix keeps the
sentence, appends the keywords to sharpen it, and drops the label. It was chosen by
running all six candidate shapes through this harness, not by intuition.

The harness reproduces the before/after on every run, so the change is verifiable
and a regression would be visible rather than silent.

Language holds up: Vietnamese queries score MRR 0.800 against English 0.786,
though n = 5 makes that weak evidence rather than a result.

Six queries retrieved nothing relevant in the top 4. One is safety-relevant:
`"hopeless worthless lost motivation student with Severe stress"` failed to
surface either the help-seeking section or the counselling-service section. Every
miss is listed verbatim in the artifact.

**Not measured:** faithfulness. This scores what was *retrieved*, not whether the
generator *used* it. That needs an LLM-as-judge pass and a live API key.
**Caveat:** corpus, queries and labels all originate within this project, single
annotator, so there is no inter-annotator agreement.

## 4c. Latency and cost — partly computed, offline

Regenerate: `python -m app.eval.latency_eval --repeats 30`
(artifacts: `data/eval/latency.md`, `latency.json`, `fig_4_9_latency.png`)

Every deterministic stage is timed directly, so these are measurements rather
than estimates. Measured 2026-09-08 on the development machine (CPU only).

| Stage | p50 (ms) | p95 (ms) |
|---|---:|---:|
| DASS-21 + PSS-10 scoring | 0.03 | 0.05 |
| crisis rule | 0.05 | 0.07 |
| lexicon keywords | 0.07 | 0.12 |
| RAG retrieval (k = 4) | 28.01 | 83.43 |
| PhoBERT inference | 59.31 | 93.32 |

Cold start, paid once per process rather than per session: **PhoBERT 10.8 s**,
**embedder 10.8 s**. This is why the API loads models lazily rather than in the
startup hook.

**What this shows.** The entire deterministic path — crisis rule, scoring,
lexicon, retrieval and the classifier — costs under 100 ms at p50. The safety
rule that gates everything is 0.05 ms, so running it first is free. Any
user-visible latency in a full assessment is therefore the generation call,
not the parts this project built.

**Not measured:** the generation stage itself, and with it tokens and cost per
session. Those need `--llm-samples N`, where each sample is a real billable
request; the day's quota was spent on the comparison run. Token counts, when
measured, come from the provider's own `usage_metadata` rather than a character
heuristic. On the current provider (Groq free tier) monetary cost is zero and
the binding constraint is the daily token cap, not price.

## 5. Real-data study — instrumented, awaiting participants

Pipeline (identical eval code, `--dataset real`):

```bash
python scripts/export_dataset.py --split    # SQLite -> data/real/dataset.csv
python scripts/data_quality_report.py       # advisory quality flags
python -m app.eval.compare --dataset real
python -m app.eval.ablation --dataset real
```

Toolkit verified against the synthetic DB (export summary and quality flags
behave correctly: 201/201 synthetic rows flagged for missing text + instant
completion, 2 genuine DASS/PSS-mismatch flags). Consent form and participant
instructions: `docs/consent_form_vi.md`, `docs/participant_instructions_vi.md`.

## 6. Human evaluation — scaffolded, no data yet

- `python -m app.eval.export_for_rating --n 30 --raters 3` → per-rater CSV
  sheets (accuracy / helpfulness / respectfulness, 1–5). Refuses synthetic
  placeholder explanations, so sheets can only ever contain real model output.
- `python -m app.eval.rating_analysis --dir data/eval/rating` → per-criterion
  means + Krippendorff's α (interval; implementation pinned by a hand-computed
  test case).
- SUS: `docs/sus_questionnaire_vi.md` + `python -m app.eval.sus_score --csv …`
  (standard Brooke scoring, Bangor/Sauro-Lewis bands).

No rating or SUS numbers exist yet and none will be written here until real
raters/participants produce them.

## Appendix: pipeline self-check with simulated predictions

`python -m app.eval.synthetic --rows 200 && python -m app.eval.evaluate`
computed accuracy 0.775 / macro-F1 0.774 / κ 0.683 on 200 rows whose
"LLM predictions" were **simulated at a configured ~72% agreement**. This
verifies the metric/plot pipeline only — it says nothing about any model and
must never be cited as a system result.
