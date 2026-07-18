# Experimental Results

Single collection point for every computed result, ready to lift into the
thesis. **Every number on this page was produced by executing the referenced
script**; nothing is estimated or hand-written. Where a result rests on
synthetic data it is labeled as such. Regeneration commands are given with
each table (figures land in `data/eval/`, which is intentionally not in git).

Last regenerated: 2026-07-18/19 on the synthetic dataset.

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
| llm_zeroshot | — | — | — | — | — | — | — | — |
| llm_full | — | — | — | — | — | — | — | — |

**Honest reading of what is there so far:**

- `tfidf_lr` currently **beats** `phobert_ft` on macro-F1 (0.682 vs 0.533).
  The gap is almost entirely the Severe class: the fine-tuned PhoBERT model is
  3-class and *cannot* predict Severe (identity 3→4 mapping; F1_severe = 0 by
  construction). On the classes it can predict, it is competitive
  (f1_low 0.842, f1_moderate 0.681, f1_high 0.609 — each ≥ tfidf_lr).
- `llm_zeroshot` and `llm_full` have produced **no numbers yet**: the
  configured `OPENAI_API_KEY` is a placeholder. Setting a real key and
  re-running the command above fills both rows from the same frozen split
  (responses are disk-cached under `data/eval/llm_cache/`, so the run is
  deterministic and repeatable at zero marginal cost).
- Validity caveat that must accompany any `llm_full` number: its prompt
  contains the DASS/PSS scores from which the ground-truth label is derived,
  so its agreement is partly by construction. The `no_questionnaire` ablation
  is the honest text-only comparison.

## 3. Ablation study — NOT RUN YET

Regenerate: `python -m app.eval.ablation --dataset synthetic`
(artifacts: `data/eval/ablation.csv`, `ablation.md`, `ablation.png`)

Requires a valid `OPENAI_API_KEY`; the runner currently writes an explicit
"NOT RUN" marker instead of a table. Configurations wired and tested (with a
mocked LLM): `full`, `no_rag`, `no_questionnaire`, `no_emotion`, `text_only` —
all through the same engine as the headline `llm_full` system. The
interpretation paragraph is generated from the computed deltas.

## 4. Crisis-detection rule — computed, offline

Regenerate: `python -m app.eval.crisis_eval`
(artifact: `data/eval/crisis_eval.md`)

Test set: 50 hand-labeled Vietnamese items (committed at
`data/eval/crisis_testset.jsonl`): 20 true positives (explicit + indirect
ideation), 20 hard negatives (hyperbole, reported speech), 10 borderline items
with annotation rationale. The rule was **not** tuned against this set.

| metric | value |
|---|---|
| precision | 0.800 |
| recall | 0.500 |
| F1 | 0.615 |

Per-category accuracy: explicit_tp 10/10 · dass_tp 1/1 · dass_neg 1/1 ·
normal_stress_neg 4/4 · hyperbole_neg 12/15 · indirect_tp 1/9 · borderline 6/10.

Failure modes as measured (full verbatim lists in `data/eval/crisis_eval.md`):

- **3 false positives** — the substring rule fires on "muốn chết" inside
  hyperbole or reported speech (items 23, 24, 40), e.g. *"Mệt muốn chết nhưng
  vẫn phải cố ôn thi cho xong."*
- **12 false negatives** — indirect ideation is almost entirely missed
  (8/9 indirect items): means-referencing plans, farewell-letter references,
  burdensomeness with a death reference, passive death wishes (4 borderline
  items labeled true).

Implication for the thesis: the deterministic rule is a high-precision
explicit-phrase detector, not an ideation detector. Its FN list is the
requirements list for any future revision (which must then be evaluated on a
*new* held-out set).

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
