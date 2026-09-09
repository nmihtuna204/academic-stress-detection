# Top 10 Committee Attack Surfaces

Companion to [AUDIT.md](AUDIT.md) and [FEATURE_MATRIX.md](FEATURE_MATRIX.md). Audited 2026-08-03 at commit `50e145a`.

Each entry gives the question the panel will actually ask, the **best answer the repository can support today**, and what would make that answer stronger. Answers marked **⚠ cannot be defended yet** are the ones to fix before the defence.

---

## R1 — The classifier was trained and tested on template-generated text

> *"Your PhoBERT model scores 0.80 macro-F1. Your text was generated from 41 Vietnamese sentence templates. What did the model actually learn?"*

**Current best answer.** It learned the templates, and the repository can say so quantitatively rather than being told. Measured on the frozen split: each test text's maximum similarity to any training text is **median 0.799, p90 0.893, max 0.907; 34 of 70 test items (49 %) exceed 0.80 and 4 exceed 0.90** (reproduce with `python scripts/check_leakage.py`; the earlier 0.808/36 figures came from an under-specified variant of the same `difflib` method and are superseded). Exact-duplicate leakage is zero (466 distinct texts, none crossing splits), which is exactly why exact-match checking is the wrong instrument here. Every text-classification figure in this project is therefore a **pipeline demonstration, not evidence of stress-detection ability** — which is precisely why the real-data collection toolkit ([scripts/export_dataset.py](../scripts/export_dataset.py)) and an identical `--dataset real` evaluation path already exist.

**⚠ Risk level: high.** This is the single most likely question and the answer is an admission. It lands far better volunteered with numbers than extracted under questioning.

**Strengthen by:** committing `scripts/check_leakage.py`, citing the measurement in the report, and — if any real data can be collected before the defence — running `--dataset real` even with 50 participants.

---

## R2 — The LLM silently overrides the validated instrument

> *"A student completes DASS-21 and scores Severe. The LLM says Moderate. What does your app show them, and on what authority?"*

**Current best answer.** It shows **Moderate** — the LLM's label — because [5_Results.py:215–221](../streamlit_app/pages/5_Results.py#L215-L221) prefers `assessment.predicted_level` and falls back to the questionnaire only when the LLM is unreachable. The prompt instructs the model to weigh all evidence and reduce its confidence when sources conflict ([chain.py:46–48](../app/llm/chain.py#L46-L48)), and the deterministic score remains visible on the same screen as sub-scores.

**⚠ Cannot be defended yet.** There is no disagreement detection, no reconciliation rule, no measurement of how often the two diverge, and no indication to the student that they did. For a screening tool, allowing an unvalidated generative model to overrule a validated psychometric instrument is a methodological choice that needs an explicit justification the repo does not currently contain.

**Strengthen by:** deciding and documenting a fusion rule (recommended: the questionnaire label is authoritative for the headline; the LLM contributes explanation and suggestions; disagreement is surfaced and logged), then reporting the disagreement rate.

> **Resolved 2026-09-05.** The recommended rule is implemented. [5_Results.py](../streamlit_app/pages/5_Results.py) now takes the headline level from `questionnaire.ground_truth_label` whenever a questionnaire exists, and falls back to the model only when there is none. Where the two differ the student is told so explicitly, and the LLM section is retitled to make clear it explains the model's own reading. `compute_metrics` reports `disagreement_rate` and `n_disagreements`. What remains open is the *measured* rate, which needs the LLM runs of R4.

---

## R3 — Crisis detection misses half the cases it was tested on

> *"Your safety net has recall 0.50. A student writes 'em chỉ muốn ngủ một giấc thật dài và không bao giờ tỉnh lại nữa' ('I just want to sleep for a very long time and never wake up again'). What happens?"*

**Current best answer.** Nothing fires — that exact sentence is false negative #16 in `data/eval/crisis_eval.md`. The rule is a high-precision explicit-phrase detector (**precision 0.800, recall 0.500, F1 0.615** on a 50-item hand-labelled set it was deliberately **not** tuned against): explicit phrasing 10/10, indirect ideation 1/9. The project measured this itself, published every false negative verbatim, and refused to tune against its own test set. Mitigations in place: the rule runs before any LLM call, the disclaimer is unavoidable, and helplines appear in the knowledge base and on the results page.

**⚠ Risk level: high** — but this is the honest-measurement question, and the answer demonstrates exactly the rigour the rubric rewards. The vulnerability is the *trade-off*, not the transparency: in a domain where false negatives cause harm, 0.80/0.50 is the wrong operating point.

**Strengthen by:** expanding the lexicon against the published FN list, explicitly accepting more false positives, and re-measuring on a **new** held-out set (never the one already used).

> **Resolved 2026-09-09.** The rule was rebuilt around six suicide-risk constructs ([crisis_patterns.py](../app/nlp/crisis_patterns.py)) rather than a longer phrase list, with span-local idiom guards. The order mattered: a 60-item bilingual held-out set was written and frozen *before* the patterns existed, the patterns were written from the construct taxonomy rather than from failing items, and the first measurement is the reported one. On that held-out set the rule moved from **P 0.600 / R 0.200 / F1 0.300** to **P 1.000 / R 0.867 / F1 0.929**, with indirect ideation from 0/14 to 11/14 and no false positives across 20 lethal-sounding idioms. The Vietnamese and English sets are now development sets and their numbers are fitted; see [RESULTS.md §4](RESULTS.md). Two things remain open: the held-out set shares an author with the patterns, and three indirect items are still missed.

---

## R4 — "LLM-powered" thesis with no LLM evaluation

> *"Your title says LLM-powered. Which table in your report evaluates the LLM?"*

**Current best answer.** None exists today. The `llm_zeroshot` and `llm_full` systems are fully implemented, unit-tested with mocked models, and wired into the same frozen split as the classical baselines — they produced no numbers only because the configured `OPENAI_API_KEY` is the literal placeholder `sk-...`. The runners write "Not run" markers instead of plausible numbers ([comparison.md](../data/eval/comparison.md), [ablation.md](../data/eval/ablation.md)). Responses are disk-cached by input hash, so a single run is deterministic and repeatable at zero marginal cost.

**⚠ Cannot be defended yet, and this one has no excuse:** two commands and one environment variable produce the baseline table and the five-configuration ablation. Beyond that, retrieval quality (Recall@k, MRR, nDCG@5), faithfulness judging, red-teaming, and latency/cost remain entirely unbuilt.

**Strengthen by:** running the two existing evaluations *first*, then building the RAG evaluation over the 23-chunk corpus (§2 of the fix list in [AUDIT.md](AUDIT.md)).

---

## R5 — The RAG layer cannot actually be ungrounded, because nothing constrains it

> *"What stops your model inventing mental-health advice when retrieval returns nothing?"*

**Current best answer.** Nothing does. `retrieve()` returns `[]` on an empty collection or any exception ([retriever.py:48–50](../app/rag/retriever.py#L48-L50)), the prompt's strongest instruction is *"grounded in the reference material provided"* — grounding as a preference, not *only* ([chain.py:40–42](../app/llm/chain.py#L40-L42)) — and `LlmAssessment` has no citation field. The results page still prints a "Reference material" line built from what was *retrieved*, not what was *used* ([5_Results.py:362](../streamlit_app/pages/5_Results.py#L362)). The partial mitigations that do exist: the crisis rule bypasses the LLM entirely, the model is forbidden diagnostic language, and suggestions are capped at 3–5 actionable items.

**⚠ Cannot be defended yet.** Fixing the prompt is an S-effort change; measuring faithfulness is M.

> **Largely resolved 2026-09-06.** Four changes. (1) The prompt's rule 4 is now an absolute grounding constraint — the model may rephrase the retrieved material but may not add advice, services, numbers or clinical claims that are not in it, and is told to say so rather than fill a gap from its own knowledge. (2) `LlmAssessment` gained a `citations` field; each retrieved block is labelled with its chunk id and the model must cite those ids. (3) The service **verifies** the returned citations against what was actually retrieved and discards any it invented, so a fabricated provenance claim cannot reach the student. (4) Empty retrieval is now an explicit refusal: the generator is not called at all, and the response carries `advice_unavailable_reason` which the results page displays. The UI now attributes advice to `cited_sources` (what was used) and relegates `rag_sources` (what was searched) to an expander. Covered by `TestGrounding` in [tests/test_api.py](../tests/test_api.py).
>
> **Still open:** faithfulness itself is unmeasured — whether the cited passage actually supports the sentence citing it needs an LLM-as-judge pass and an API key. Retrieval quality, however, is now measured: see [RESULTS.md §4b](RESULTS.md) and `data/eval/retrieval_eval.md`.

---

## R6 — Neither Vietnamese instrument is verifiably the validated translation

> *"Which validated Vietnamese version of DASS-21 did you use, and can you show the item-by-item correspondence?"*

**Current best answer.** [dass21.py:8–10](../app/scoring/dass21.py#L8-L10) cites the Vietnamese adaptation attributed to Tran et al. (2013, BMC Psychiatry) *"with minor smoothing for a student audience"* — so by the code's own admission the deployed wording is **not** the validated instrument, and the deviation is nowhere documented. The Vietnamese PSS-10 wording carries **no citation at all**. Separately, the PSS-10 docstring calls its 0–13/14–26/27–40 bands "Cohen's official scoring", but Cohen published normative means, not clinical cut-offs — the bands are a widely-used convention.

**⚠ Cannot be defended yet.** The arithmetic is provably correct (100 % test coverage, verified against the manual); the *linguistic* validity is unsupported, and one citation is overstated.

**Strengthen by:** obtaining the published Vietnamese item lists, diffing them item by item into Appendix A, removing the word "official", and citing the convention's actual source.

---

## R7 — The consent the app obtains is thinner than the consent the study document promises

> *"Does the student know their private writing is sent to a company in the United States?"*

**Current best answer.** [docs/consent_form_vi.md](consent_form_vi.md) §4 states it clearly. The **in-app** consent — the only thing an actual user reads — reduces consent to three bullets (age ≥ 18, screening not diagnosis, voluntary anonymous storage) and never mentions OpenAI, retention, or deletion ([Home.py:78–82](../streamlit_app/Home.py#L78-L82)). Genuine protections are real: UUID-only identity, no name/email/student number, no identifiers in any prompt, and demographics stripped from the research export.

**⚠ Cannot be defended yet** — and it is an S-effort fix (three bullets). Leaving it is a needless ethics finding on a mental-health application.

> **Resolved 2026-09-05.** The in-app consent list in [Home.py](../streamlit_app/Home.py) now states third-party processing by OpenAI in the United States, the 12-month retention period, and the right to erase, matching what [consent_form_vi.md](consent_form_vi.md) §4–§6 promises.

---

## R8 — Data is retained forever, in plaintext, with no way to delete it

> *"A participant emails you next month asking you to delete their entry. What do you do?"*

**Current best answer.** Manually edit the SQLite file. The API exposes no `DELETE` route ([api/main.py](../app/api/main.py)), the UI offers no control, there is no retention policy and no encryption at rest ([database.py:29](../app/db/database.py#L29)). Worse for the crisis path: free text is persisted **before** the crisis check runs ([main.py:72–74](../app/api/main.py#L72-L74), [services.py:168,184](../app/api/services.py#L168)), so exactly the most sensitive disclosures are stored raw. `GET /history/{student_id}` returns `raw_text` with no authorisation — practically protected only by UUID4 unguessability.

**⚠ Cannot be defended yet.** All three fixes (reorder two calls, add `DELETE /session/{id}` + a button, state a retention period) are S-effort.

> **Resolved 2026-09-05.** All three are done. The crisis rule now runs before any write on all three assessment endpoints, so a self-harm disclosure is never persisted; only the trigger reasons are logged. `DELETE /session/{student_id}` erases every row across the five tables and is exposed as a two-step control on the History page. The retention period is stated in the in-app consent. Covered by `TestCrisisDisclosuresAreNotRetained` and `TestDeleteSession` in [tests/test_api.py](../tests/test_api.py). Still open: no encryption at rest, and `GET /history/{id}` remains authorised only by UUID unguessability.

---

## R9 — Single seed, no statistics, missing baselines

> *"tfidf_lr scores 0.682 and phobert_ft 0.533. Is that difference real?"*

**Current best answer.** Unknown — every number in the repo comes from one seed with no confidence interval and no significance test. What *can* be said precisely is that the gap is almost entirely structural, not qualitative: the fine-tuned model is 3-class and cannot emit "Severe", so `f1_severe = 0` by construction under the documented identity 3→4 mapping. On the three classes it can predict it is **at or above** tfidf_lr on every one (f1_low 0.842, f1_moderate 0.681, f1_high 0.609). Both systems ran on the identical frozen split, and the exact evaluated dataframe is written to disk on every run.

**Partially defensible.** The structural explanation is strong and already documented in [DECISIONS.md](../DECISIONS.md). The missing pieces — majority-class baseline in the 4-class harness, SVM, few-shot LLM, ≥3 seeds with mean ± std, bootstrap CIs, McNemar — are all standard and all absent.

---

## R10 — Results cannot be reproduced end to end

> *"Walk me from the raw generator to the number in your table."*

**Current best answer.** Most of the chain is solid: the generator is seeded, the split is frozen and reused (deliberately, so no fine-tuning data leaks into test), ingestion is idempotent, LLM responses are hash-cached, and the exact evaluated dataframe is persisted on every run. **The chain breaks in one place:** `research/baseline.py` consumes `data/stress_dataset_clean.csv` (466 rows, 11 columns), and **no script in the repository produces that file** from `data/stress_dataset.csv` (500 rows, 75 columns). I could reconstruct the transform — the raw file has exactly 466 unique `free_text` values, so it was an exact-dedup plus a column projection — but reconstruction is not documentation.

Two further reproducibility issues: **all 21 dependencies are unpinned** (`>=` only), and **`data/eval/` is gitignored**, so no result artefact backing the report is under version control.

**⚠ Partially defensible.** All three fixes are S-effort: write the missing script, `pip freeze` into a pinned requirements file, and redirect (or un-ignore) result artefacts.

---

## Priority ordering for defence preparation

| Rank | Risk | Effort to make defensible | Why first |
|---:|---|---|---|
| 1 | R4 — no LLM evaluation | **XS** for the two existing runners | Two commands close the gap the title creates |
| 2 | R7 + R8 — consent, deletion, crisis-text storage | **S** | Ethics findings on a mental-health app; all trivially fixable |
| 3 | R1 — near-duplicate leakage | **S** | Turns the sharpest attack into evidence of rigour |
| 4 | R2 — LLM overrides the instrument | **S** decision, **M** to measure | A design choice the panel will not accept as an accident |
| 5 | R5 — no grounding constraint | **S** prompt, **M** measurement | Core to the RAG claim |
| 6 | R10 — reproducibility chain | **S** | Cheap, and R1/R4 evidence depends on it |
| 7 | R6 — instrument provenance | **M** | Needs sourcing the published translations |
| 8 | R3 — crisis recall | **M** | Needs a *new* held-out set after any change |
| 9 | R9 — statistics and baselines | **M** | Real, but lower value until the data story is fixed |

**Read alongside:** the fix list at the end of [AUDIT.md](AUDIT.md), which orders the same work by grade impact ÷ effort.
