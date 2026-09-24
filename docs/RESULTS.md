# Experimental Results

Single collection point for every computed result, ready to lift into the
thesis. **Every number on this page was produced by executing the referenced
script**; nothing is estimated or hand-written. Where a result rests on
synthetic data it is labeled as such. Regeneration commands are given with
each table (figures land in `data/eval/`, which is intentionally not in git).

Last regenerated: 2026-07-18/19 on the synthetic dataset; the crisis-rule and
retrieval-quality sections re-run 2026-09-06; `llm_full` and the faithfulness
section re-run 2026-09-19 after the cache contamination in §2; the ablation
completed 2026-09-20 (all five configurations, §3).

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
| llm_full | 70 | 0.6714 | 0.6495 | 0.5764 | 0.8889 | 0.8500 | 0.3448 | 0.5143 |

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
> **Correction, 2026-09-19. Every `llm_full` number published before this date
> was contaminated.** The LLM cache held 85 stub entries written by a test on
> 2026-09-09 (reasoning `"x"`, suggestions `["a"]`, label Moderate or High). The
> cache key hashes inputs only, so real runs served those stubs as model output:
> **24 of the 70 `llm_full` predictions**, 14/40 of the ablation's `full`
> configuration and **40/40 of `no_questionnaire`**. The stubs are quarantined
> (`data/eval/llm_cache_quarantine_2026-09-09_test_stubs/`, kept as evidence),
> every affected item was regenerated, and `tests/conftest.py` now fails any
> test that writes to the real cache. The withdrawn figures were accuracy 0.4857
> / macro-F1 0.5000 / kappa 0.3105, and the conclusion drawn from them - "the
> full system does not beat zero-shot" - is reversed below. `llm_zeroshot` and
> the offline systems were unaffected.

**Paired re-analysis, 2026-09-24** (`python scripts/comparison_paired.py`; plan
fixed in the script before running; post hoc relative to this table). All six
systems are scored on the same 70 items, so each comparison is paired. The
script reads the published predictions back — `llm_full` under its pre-pinning
cache keys, with a stub client that fails on any cache miss — and reproduces all
six rows exactly before testing anything.

| `llm_full` against | `llm_full` alone correct | other alone correct | McNemar p | Holm p (×5) | ΔQWK (other − full), 95 % CI |
|---|---:|---:|---:|---:|---|
| llm_zeroshot | 13 | 3 | 0.021 | **0.085** | −0.075 [−0.133, −0.031] |
| tfidf_lr | 9 | 10 | 1.000 | 1.000 | −0.031 [−0.093, +0.021] |
| tfidf_svm | 9 | 8 | 1.000 | 1.000 | −0.045 [−0.109, +0.007] |
| phobert_ft | 13 | 12 | 1.000 | 1.000 | −0.073 [−0.131, −0.012] |
| majority | 30 | 6 | 0.0001 | 0.0005 | −0.871 [−0.914, −0.816] |

- **The full system leads zero-shot, but the lead is not established.**
  `llm_full` reaches macro-F1 **0.649** against zero-shot's 0.524 (kappa 0.576
  vs 0.389), `unusable=0` on all 70 items, and is right alone on 13 items to
  zero-shot's 3. As a single comparison that is significant (McNemar p = 0.021);
  under the Holm correction across the five comparisons, which was the
  pre-specified analysis, it is not (p = 0.085). QWK favours `llm_full`
  descriptively. This section previously called the lead "clear"; that
  overstated it, and the word is withdrawn.
- **It is indistinguishable from the classical baseline** — and from PhoBERT and
  the SVM. Against TF-IDF + LR the disagreements split 9 to 10. (This section
  previously reached the same conclusion with a single-proportion "noise floor"
  of ±0.117; the conclusion stands, the paired test is the right way to reach
  it.) On template-generated text a bag of n-grams is very good at recognising 41
  recurring templates, which is precisely the criticism §5.3 makes of the
  dataset.
- **`llm_full` receives the scores that define the label**, so leakage was
  possible by construction. The ablation (§3; 40-item subsample, pinned pipeline)
  finds it does not happen: removing the scores leaves accuracy unchanged. So
  leakage is not what separates `llm_full` from zero-shot.
- **Its weak class is High (F1 0.345),** the class the questionnaire rule places
  between two neighbours.

## 2b. PhoBERT fine-tuning — multi-seed, and a 4-class checkpoint that is not deployed

Train: `python research/phobert_finetune.py --labels 4 --segment none --seeds 13 42 7 --save-best-to models/phobert-stress-4c`
(record: `data/eval/phobert_finetune.md`, `data/eval/phobert_runs/*.json`).
Verify and compare: `python scripts/phobert_checkpoint_compare.py`.

The `phobert_ft` row in §2 is the checkpoint the application loads,
`models/phobert-stress`: a **3-class** model (Low / Moderate / High), trained
once, on one seed. It cannot output Severe, so its Severe F1 of 0.000 is a
property of its label space, not of its training — and that zero is most of
the gap between its macro-F1 and everyone else's.

**Multi-seed study.** The same frozen split, 4 classes, inverse-frequency class
weights computed on train only, test scored once per seed and never used for
selection:

| segmentation | seeds | test accuracy | test macro-F1 | test kappa |
|---|---:|---:|---:|---:|
| none | 13, 42, 7 | 0.643 ± 0.000 | 0.614 ± 0.003 | 0.526 ± 0.008 |
| VnCoreNLP | 13, 42, 7 | 0.610 ± 0.036 | 0.577 ± 0.032 | 0.483 ± 0.056 |

Unsegmented input does better here, against the PhoBERT paper's recommendation
to word-segment — worth knowing before citing it.

**The checkpoint.** `models/phobert-stress-4c` is seed 7, the best on
*validation* (macro-F1 0.661). On 2026-09-24 its saved weights were re-run on
validation and test and reproduced the training record exactly (0.7143 / 0.6613
and 0.6429 / 0.6128). It is not in git (540 MB); the command above regenerates it.

**Is it better than the deployed model?** Paired on the same 70 test items; plan
fixed in the script before running; one pre-specified primary comparison:

| | accuracy | macro-F1 | QWK | within ±1 level | F1 Severe |
|---|---:|---:|---:|---:|---:|
| 4-class checkpoint | 0.643 | 0.613 | 0.830 | 0.986 | 0.621 |
| 3-class, deployed | 0.657 | 0.533 | 0.798 | 1.000 | 0.000 |
| `llm_full` | 0.671 | 0.649 | 0.871 | 1.000 | 0.514 |
| `tfidf_lr` | 0.686 | 0.682 | 0.840 | 0.986 | 0.667 |

- **No.** On 19 items one is right where the other is wrong, and they split 9
  to 10 (exact McNemar p = 1.00); ΔQWK −0.033 [−0.088, +0.029]. The macro-F1 gain, 0.533 → 0.613, is
  the Severe class becoming predictable at all, not better classification.
- **Against `llm_full` and TF-IDF it is indistinguishable** (5 vs 7 and 4 vs 7,
  Holm p = 1.00 for both).
- **So the question RISKS R9 asks — is TF-IDF's 0.682 against PhoBERT's 0.533
  real? — has an answer: no.** TF-IDF is right alone on 10 items, the 3-class
  model on 8, McNemar p = 0.81. The macro-F1 gap is the Severe zero.
- **Correction.** Commit `9445a95` attributed the Severe improvement across seeds
  to class weights. It comes from training in the 4-class label space; the
  deployed model could never have predicted Severe.

**Why it is not deployed.** There is no measured gain to deploy. And every
published LLM result — the `llm_full` comparison, the ablation, faithfulness —
was produced with the 3-class model's reading in its prompt, while the LLM cache
key covers the text but not the classifier. Swapping the checkpoint without
changing the key would serve replies generated from the old model's reading as
though they came from the new one: the same silent staleness as the
contamination in §2. Doing it properly means a key change and about two days of
provider quota to regenerate those results, which is not worth spending on a
change with no measured benefit. The case to revisit it is real data with Severe
cases, where a model that can say "Severe" might matter.

## 3. Ablation study — complete, re-run 2026-09-20; paired analysis 2026-09-24

Regenerate: `python -m app.eval.ablation --dataset synthetic --limit 40`
(artifacts: `data/eval/ablation.csv`, `ablation_paired.csv`, `ablation.md`,
`ablation.png`). Once the cache is warm a re-run makes no API calls; the
2026-09-24 regeneration left the cache at 495 entries before and after.

Stratified 40/70-item subsample, seed 42, identical across configurations. All
five configurations have 40/40 real model replies: the completing run made 78
live calls with **zero rate-limit refusals and zero parse failures**.

| config | accuracy | within ±1 level | macro-F1 | kappa | QWK |
|---|---:|---:|---:|---:|---:|
| full | 0.675 | 1.000 | 0.6399 | 0.5847 | 0.874 |
| no_rag | 0.675 | 1.000 | 0.6262 | 0.5860 | 0.874 |
| no_questionnaire | 0.675 | 1.000 | 0.5467 | 0.5390 | 0.804 |
| no_emotion | 0.550 | 1.000 | 0.5364 | 0.4231 | 0.822 |
| text_only | 0.525 | 1.000 | 0.4923 | 0.3537 | 0.768 |

**How the comparisons are tested, and why that changed.** The run was specified
against a "noise floor" of ±0.148: the 95 % Wilson half-width of *one* accuracy
at n = 40. That is not the right yardstick for these comparisons. Every
configuration is scored on the same 40 items, so each comparison is paired, and
the information about a difference lies in the items the two configurations
classify differently. The harness now uses the textbook paired test — **exact
McNemar on accuracy, Holm-corrected across the four comparisons, α = 0.05** —
pre-specified in its docstring for every future run. For *this* run it was
adopted after the results were known, so it is **post hoc** here, and it was
fixed in writing before any paired number was computed.

| removed | full alone correct | ablated alone correct | Δ accuracy | McNemar p | Holm p | ΔQWK, paired bootstrap 95 % CI |
|---|---:|---:|---:|---:|---:|---|
| RAG | 1 | 1 | 0.000 | 1.000 | 1.000 | +0.001 [−0.021, +0.023] |
| questionnaire | 7 | 7 | 0.000 | 1.000 | 1.000 | −0.070 [−0.150, +0.013] |
| emotion features | 6 | 1 | −0.125 | 0.125 | 0.500 | −0.052 [−0.109, −0.007] |
| everything but text | 11 | 5 | −0.150 | 0.210 | 0.630 | −0.106 [−0.204, −0.029] |

- **The primary result is still null.** No removal produces a difference in
  accuracy that the paired test distinguishes from chance. The better test did
  not rescue the ablation, and it should not be cited as though it had shown a
  component to matter.
- **But the null now says two different things.** For RAG and the
  questionnaire, the disagreements cancel exactly (1 against 1, 7 against 7):
  that is an effect on accuracy close to zero, and no larger sample would make
  it significant. For the emotion features and for stripping everything, the
  disagreements run one way (6 against 1, 11 against 5): a consistent direction
  that 40 items are too few to establish.
- **How many items would settle it.** Resampling the observed pairs, the
  McNemar test would reject for `no_emotion` in 66 % of samples at n = 70, 85 %
  at n = 100 and 96 % at n = 150; for `text_only`, 44 %, 61 % and 81 %. That is
  per comparison and before the Holm correction, and projections from a small
  sample are optimistic — read them as upper bounds. The earlier statement here
  that "n ≈ 600" would be needed described a 0.05 effect, not the effects actually
  observed; for those, 100–150 paired items is the order of magnitude. The whole
  test split is 70.
- **Descriptively, QWK moves where accuracy does not.** The ΔQWK intervals for
  `no_emotion` and `text_only` exclude zero. These were designated descriptive
  before the analysis, are uncorrected, and are 2 of 20 intervals examined, so
  they are suggestive and nothing more — but they are a reason to pre-specify
  QWK as the primary metric for the thesis-phase study.

**Every error, in every configuration, is exactly one level off.** Mean absolute
error in levels equals 1 − accuracy in all five, which is only possible if no
prediction is ever more than one level from the truth (the `within ±1 level`
column). The full pipeline is exactly right on 67.5 % of items and adjacent on
the rest, QWK 0.874. Exact-match accuracy makes it look worse than it behaves.

**The LLM does not reproduce the instrument's label, even with the instrument's
results in front of it.** In `full`, the prompt carries the scored DASS-21 and
PSS-10 results — though not the rule that combines them into the label — and
the model still assigns a different level from the instrument on 32.5 % of items.
Removing those results does not lower accuracy at all (0.675 either way).
Two consequences:

- The caveat that the questionnaire defines the label, so `no_questionnaire`
  might "measure label leakage", is correct in principle but did not happen: the
  model is not exploiting the leak.
- It is direct evidence for a design decision made earlier on other grounds. The
  application takes its headline level from the validated instrument and uses the
  LLM for explanation and grounded advice only; a model that disagrees with the
  instrument a third of the time, even when shown its scores, should not be the
  source of the headline.

**The earlier "questionnaire removal collapses macro-F1 by 0.411" is
withdrawn.** That run's `no_questionnaire` predictions were 40/40 test stubs (see
the §2 correction), so it measured the constant-Moderate floor.

**Why `full`, `no_questionnaire` and `no_emotion` differ from the 2026-09-19
run.** Support-passage pinning (§4b) entered the cache key after that run, and
it fires for 32 of the 40 items in `full` and `no_emotion` — those items were
therefore regenerated with the pinned help-seeking passages in context.
`no_questionnaire` changed for a different reason: its 2026-09-19 pass was cut
short by the daily token cap. `no_rag` and `text_only` do not use retrieval, so
their keys were untouched, and **`no_rag` reproduced its previous numbers to
four decimal places** — an unintended control that confirms the mechanism.

**A safety intervention with a measurable cost.** Pinning was added so that rule
6 (encourage professional support) has material to work from in severe cases;
before it, support-resource passages were retrieved for 0 of 70 test items. It
moved `full` from macro-F1 0.673 to 0.640. That is one descriptive difference
between two runs, untested and not claimed as established, but it is in the
direction of a real trade-off and is reported rather than omitted.

**Residual caveat — checked, and narrower than first stated.** `full_cache_key`
carries a `query_shape` field that was not bumped when the lexicon-ordering
defect was fixed, and 3 of the 40 items (positions 1, 20, 27) retrieve a
different top 4 under some keyword orders. Cache timestamps settle which replies
could be stale: for those items, `full` and `no_emotion` were regenerated on
2026-09-20 between 21:18 and 21:57, after the fix, and `no_rag` and `text_only`
do not retrieve at all. **Only `no_questionnaire`'s three replies** (2026-09-19,
19:16–19:22) may predate it. Flipping all three in the least favourable
direction moves that comparison from 7 against 7 to at best 7 against 4, McNemar
p = 0.549: no conclusion above can change. So no re-run was needed — the earlier
plan to bump the key and regenerate 120 replies (~216 K tokens) would have spent
more than a day's allowance on something that cannot move the result.

**Schema defect found by this run, fixed.** With no retrieved material the model
follows prompt rule 4 and returns `"suggestions": []`, stating in its reasoning
that no reference material was provided. `LlmAssessment` rejected that with
`min_length=1`, turning a correct refusal into a parse failure and a fallback
label. The floor is removed, and the service now tells the student when advice
was withheld (`advice_unavailable_reason`). The schema text inside the prompt
changed with it (no `minItems`), so rows generated before and after 2026-09-19
used marginally different format instructions.

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
each mapped to the chunk ids that genuinely answer it, over the 23-chunk corpus.
Binary relevance.

**Deployed query form: MRR = 0.844, Recall@4 = 0.961; 2 of 51 queries have no
relevant chunk in the top 4.** That is the 51 natural queries passed through
`build_rag_query()`, exactly as the deployed service sends them, at the deployed
depth k = 4. It is the figure that describes the system.

> **Correction, 2026-09-24.** Until this date the section led with **MRR 0.787**,
> and so did the report. That figure describes no query production sends: it
> scored the 51 natural queries as *raw* sentences (production appends lexicon
> keywords) together with 6 `keywords` queries that deliberately reproduce the
> query shape **retired on 2026-09-06**, kept only as a regression guard. It
> understated the deployed system. The harness now leads with the deployed form,
> and labels the set-as-written table below as what it is.

The query set as written (57 queries, MRR 0.787 — not a measure of the deployed
system):

| k | Recall@k | Precision@k | nDCG@k |
|---:|---:|---:|---:|
| 1 | 0.658 | 0.684 | 0.684 |
| 3 | 0.838 | 0.298 | 0.776 |
| 5 | 0.903 | 0.200 | 0.807 |
| 8 | 0.965 | 0.136 | 0.829 |

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

Language holds up in the query set as written: Vietnamese queries score MRR 0.800
against English 0.786, though n = 5 makes that weak evidence rather than a result.

**Misses, and a withdrawn safety concern.** In deployed form, 2 of 51 queries
retrieve nothing relevant in the top 4 (#4, #8; both listed verbatim in the
artifact). This section previously reported six, one of them safety-relevant:
`"hopeless worthless lost motivation student with Severe stress"` missing the
help-seeking material. **That concern is withdrawn** — it is one of the
retired-shape queries, and no production query takes that form. In deployed form,
**9 of 9** natural queries whose labels include a support-resource chunk retrieve
one in the top 4.

**The gap that is real.** All nine of those queries are *explicit* help-seeking
("free mental health hotline", "does my university offer counselling"). None
tests a student who describes distress *without* asking for help, which is the
case that matters for safety. Pinning covers severe questionnaire results; the
retriever's own behaviour on such text is **unmeasured**. Ten implicit-distress
queries (7 EN, 3 VI) were written, scope-checked against the crisis rule (all
ten below the gate, so production retrieves for them) and frozen before being run
on anything — see [`docs/REVIEW_implicit_retrieval_queries.md`](REVIEW_implicit_retrieval_queries.md).
Their labels were proposed by a model and count only once the author has reviewed
them; **they have deliberately not been run.**

**Retrieval is pulled toward the coping file, and the cause is identified.**
`02_coping_strategies.md` is 22 % of the corpus and 25 % of labelled-relevant
chunks, but fills 35 % of top-4 slots and 38 % of the *irrelevant* ones, while
`01_academic_stress.md` (17 % of the corpus) gets 9 %. One chunk,
`02_coping_strategies.md::4` ("A note on harmful coping", 53 words), is in the top
4 for 21 of 51 queries and relevant to 2. Both deployed-form misses expected an
`01_academic_stress` chunk and received coping chunks in 3 and 4 of their 4 slots.

Ingest prepends the document title to every chunk, and the coping file's title,
*"Strategies for coping with academic stress"*, is close to a paraphrase of the
whole query distribution. That was tested directly rather than argued
(`python scripts/hub_experiment.py`): the corpus was rebuilt in memory with and
without the title (`data/chroma` untouched), and the with-title build reproduced
the production MRR to six decimal places before anything was compared — the
script refuses to report otherwise.

| | with title (deployed) | title removed |
|---|---:|---:|
| coping share of top-4 slots | 35 % | **24 %** |
| k-occurrence skewness (hubness) | 1.18 | **0.40** |
| `02_coping::4` in top 4, of 51 | 21 | 18 |
| MRR, 51 natural queries | 0.844 | 0.804 |
| deployed-form misses | #4, #8 | #12, #13, #14 |
| questionnaire branch: actionable share | 69 % | **41 %** |
| questionnaire branch: matched subscale | 100 % | **78 %** |

- **The title is the main cause of the source-level pull** — removing it brings
  the coping share down to roughly its corpus share, and hubness falls sharply.
- **It does not explain the single hub**: `::4` stays on top without it. Its
  content, a list of generic behaviours (all-nighters, caffeine, skipped meals,
  isolation), is central on its own.
- **Removing the title is not a fix, and was not adopted.** On text queries it
  moves the bias rather than removing it — #4 and #8 recover, but #12–#14, all
  coping questions, are now pulled toward `01_academic_stress`; the MRR change,
  −0.039, is not distinguishable from zero (paired bootstrap 95 % CI [−0.126,
  +0.042]). On the questionnaire branch it is a clear regression, and that
  measurement covers all 27 DASS profiles exhaustively, so it is not a sampling
  question: the query there asks for coping strategies, and the title is what
  lets it find them.

**Caveat:** corpus, queries and labels all originate within this project, single
annotator, so there is no inter-annotator agreement.

### Faithfulness of generated advice — computed 2026-09-19

Regenerate: `python -m app.eval.faithfulness_eval --limit 40`
(artifacts: `data/eval/faithfulness_eval.md`, `faithfulness_judgments.csv`)

Each suggestion the classification run already produced is judged against the
four passages the production query retrieves for that item, by
`qwen/qwen3.8-27b` - a different model family from the generator, so it is not
grading its own phrasing. `supported` = the action and every specific detail are
in a passage; `partial` = the core action is, but a detail was added;
`unsupported` = the core action is in no passage. The `no_rag` configuration is
the control: its suggestions were written with no reference material.

| arm | items advised | suggestions | supported | supported or partial |
|---|---:|---:|---:|---:|
| full (with RAG) | 40/40 | 121 | **75 %** [0.67, 0.82] | **99 %** [0.95, 1.00] |
| no_rag (control) | 1/40 | 1 | 0 % | 0 % |

- **The strongest evidence is the refusal behaviour.** Without retrieved
  material the generator declined to advise on **39/40 items** (36 with an empty
  list, 3 by writing a refusal where the advice would go). With retrieval it
  advised on 40/40. That is prompt rule 4 working end to end.
- **One suggestion of 121 was judged unsupported** ("talk to a trusted friend or
  join a study group"). The knowledge base does contain it
  (`02_coping_strategies.md::3`), and that item is one of the three whose top-4
  depended on keyword order before the fix below, so the generator most likely
  saw that passage and the judge did not. Excluding those three items, 100 % of
  112 suggestions are supported or partial.
- **Every unsupported suggestion is help-seeking or connection advice.** Besides
  that one, the control's single suggestion was "reach out to your university's
  counselling service", written with no material at all — prompt rule 6
  (encourage professional support) overriding rule 4 once in 40. These are
  exactly the passages that went unretrieved, which is the gap support pinning
  was later added to close.
- **These rates describe the pipeline *before* support pinning.** On
  2026-09-24 the passages behind every judgment were recovered from the judge
  cache (below), and all 41 judged item-arms match the ranked-only passage
  list — none included a pinned passage. The generator's suggestions predate
  pinning too. **The deployed pipeline's faithfulness is unmeasured**, and
  whether pinning closes the gap above is a hypothesis, not a result.

**Judge validation — second rater, human rating pending (2026-09-24).**

`--export-rating` had never worked on the real judgments: it selected a
`passages` column that the published `faithfulness_judgments.csv`, written by an
older revision of `run()`, does not have. The fixtures always carried the
column, so the tests stayed green while the one route to human validation was
broken. Rebuilding the passages with today's retrieval would have shown a rater
something the judge never saw, so they are recovered instead from the judge
cache: its key hashes the passages together with the suggestions, so a candidate
passage list whose key is present is byte-identical to the judge's input. All
122 suggestions were recovered this way; any that could not be now raises rather
than being guessed.

As a check on how much the rates depend on the choice of judge, a blind 30-row
sheet (stratified by the judge's verdict so the rare verdicts are represented;
seed 42) was rated independently by a second model — Claude, a third model
family — using the judge's own rubric, with its verdicts written and hashed
before the key was opened. Reproduce with
`python -m app.eval.faithfulness_eval --agreement-second-rater`
(`faithfulness_second_rater.csv` against `faithfulness_second_rater_key.csv`):

| | |
|---|---|
| raw agreement | 27 / 30 (90 %) |
| Cohen's κ, three classes | **0.808**, bootstrap 95 % CI [0.56, 1.00] |
| κ on "unsupported" vs the rest | 1.000 |

All three disagreements run the same way: the judge said `partial` where the
second rater said `supported` — on a rationale clause, on examples given for a
supported trigger, and on one substituted list item. The judge is the stricter
of the two, so 75 % "supported" is not inflated by its leniency; and the two
raters agree exactly on what is unsupported.

The **human sheet is a separate draw** (`faithfulness_rating_sheet.csv`, seed 7),
because the second model's verdicts on the seed-42 sheet were discussed in the
working session and would anchor a rater who had seen them. It draws unseen rows
first; the only two it shares with the earlier sheet are the only two
`unsupported` rows in the whole set, which any sheet covering that verdict must
include, and the key marks them `seen_before`. Instructions, including the
verbatim rubric: [`docs/RATING_faithfulness.md`](RATING_faithfulness.md).

**What this does not establish:** human validity. It is agreement between two
models, which can share blind spots, on a sample stratified toward disagreement,
with a wide interval. It shows the published rates are robust to *which model*
judges; whether either model judges as a person would is what the human sheet is
for, and until it is filled in the rates remain a model's opinion. Synthetic
inputs, n = 40.

**Retrieval was non-deterministic across processes; found by this analysis and
fixed.** `ALL_KEYWORDS` was sorted by length only, from a set, so equal-length
keywords kept the interpreter's hash order, which changes on every start. That
is the order in which `build_rag_query` appends keywords, so the same sentence
could retrieve different passages in different runs: 3 of 40 evaluation items
changed their top-4 set. Sorting now breaks ties alphabetically, and a test runs
the import under three `PYTHONHASHSEED` values. The retrieval-quality table above
is unaffected (its queries are fixed strings; the re-run was byte-identical).

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
