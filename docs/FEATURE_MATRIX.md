# Feature Matrix

Companion to [AUDIT.md](AUDIT.md). Audited at commit `50e145a` + uncommitted UI work, 2026-08-03.
**Re-verified 2026-09-08** by re-running the suite, the linter and the evaluation harness. Rows
changed since the original audit are marked with the date they were verified; the original
status is kept in parentheses so the delta is visible rather than quietly overwritten.

**Status** — Done · Partial · Missing · Broken
**Effort** — S ≤ half a day · M ≈ 1–3 days · L > 3 days
**Grade impact** — H / M / L against the pre-thesis rubric

---

## 1. Core application

| Feature | Status | Evidence | Effort | Impact |
|---|---|---|---|---|
| DASS-21 scoring per published manual | **Done** | [app/scoring/dass21.py:25-47](../app/scoring/dass21.py#L25-L47), 150; 15 tests | — | — |
| PSS-10 scoring, reverse items 4/5/7/8 | **Done** | [app/scoring/pss10.py:13,91](../app/scoring/pss10.py#L13); 13 tests | — | — |
| PSS-10 cut-offs described as "official" | **Broken** (claim, not code) | [pss10.py:3-5](../app/scoring/pss10.py#L3-L5) — Cohen published norms, not cut-offs | S | M |
| Vietnamese DASS-21 wording traceable to the validated version | **Partial** | [dass21.py:8-10](../app/scoring/dass21.py#L8-L10) says "with minor smoothing"; no item-level diff | M | H |
| Vietnamese PSS-10 wording cited at all | **Missing** | [pss10.py](../app/scoring/pss10.py) has no source | M | H |
| Unified 4-class label (`derive_ground_truth`) | **Done** (unvalidated by design) | [scoring/__init__.py:28-51](../app/scoring/__init__.py#L28-L51) | — | — |
| PhoBERT stress classifier, local + offline | **Done** | [nlp/emotion.py:60-78](../app/nlp/emotion.py#L60-L78); `models/phobert-stress` | — | — |
| Vietnamese stress lexicon (112 terms) | **Done** | [nlp/lexicon.py:14-62](../app/nlp/lexicon.py#L14-L62), 100 % covered | — | — |
| VnCoreNLP word segmentation | **Missing** (consistent at train + inference, so not silently harmful) | [phobert_finetune.py:8-12](../research/phobert_finetune.py#L8-L12) | M | M |
| FastAPI: 5 routes, Pydantic schemas, `/health` | **Done** | [api/main.py](../app/api/main.py) | — | — |
| Graceful degradation when the LLM is unavailable | **Done** | [services.py:204-215](../app/api/services.py#L204-L215) | — | — |
| Structured logging | **Partial** | module `logging` only; no structured/JSON handler, no request ids | S | L |
| RAG ingestion, idempotent, heading-chunked | **Done** | [rag/ingest.py](../app/rag/ingest.py); 23 chunks verified | — | — |
| Multilingual embeddings for Vietnamese | **Partial** (2026-09-08) — `sentence-transformers` is now a declared dependency, so a fresh install no longer silently gets the English ONNX model; the silent-fallback branch itself remains | [store.py:32](../app/rag/store.py#L32), [requirements.txt](../requirements.txt) | S | M |
| Retrieval top-k | **Done** (k=4 hardcoded) | [services.py:200](../app/api/services.py#L200) | S | L |
| Similarity threshold / reranking | **Missing** | — | M | M |
| "Answer only from retrieved context" constraint | **Done** (2026-09-06) — rule 4 is absolute; empty retrieval refuses instead of answering *(was Missing)* | [llm/chain.py](../app/llm/chain.py) rule 4 | — | — |
| Per-claim citation/grounding in LLM output | **Done** (2026-09-06) — `LlmAssessment.citations`, verified against what was retrieved *(was Missing)* | [schemas/models.py](../app/schemas/models.py), [services.py](../app/api/services.py) | — | — |
| Behaviour on retrieval failure | **Done** (2026-09-06) — generator is not called at all; response carries `advice_unavailable_reason`, shown to the student | [services.py](../app/api/services.py), `TestGrounding` | — | — |
| LLM → structured `LlmAssessment` via Pydantic parser | **Done** | [chain.py:154-180](../app/llm/chain.py#L154-L180) | — | — |
| Fusion rule when LLM and questionnaire disagree | **Done** (2026-09-05) — instrument is authoritative for the headline; divergence shown to the student; rate reported by `compute_metrics`. Rate itself unmeasured pending the LLM runs | [5_Results.py](../streamlit_app/pages/5_Results.py) | — | — |
| SQLite persistence, 5 tables, UUID keys | **Done** | [db/models.py](../app/db/models.py) | — | — |

## 2. Safety, privacy, ethics

| Feature | Status | Evidence | Effort | Impact |
|---|---|---|---|---|
| Crisis rule runs before any LLM call | **Done** | [services.py:184-197](../app/api/services.py#L184-L197) | — | — |
| Crisis UI: suppresses analysis, shows helplines | **Done** | [5_Results.py:201-209](../streamlit_app/pages/5_Results.py#L201-L209) | — | — |
| Vietnamese helplines present and correct | **Done** (undated) | [llm/safety.py:20-37](../app/llm/safety.py#L20-L37) | S | L |
| Crisis rule measured on a held-out set | **Done** | `data/eval/crisis_eval.md` — P 0.800 / R 0.500 / F1 0.615 | — | — |
| Crisis recall adequate for a screening tool | **Broken** — misses 8/9 indirect ideation items | same | M | **H** |
| Non-diagnostic disclaimer before first input | **Done** | [Home.py:68-73](../streamlit_app/Home.py#L68-L73), every API response | — | — |
| LLM forbidden from diagnostic language | **Done** | [chain.py:34-36](../app/llm/chain.py#L34-L36) | — | — |
| Consent gate on every page | **Done** | `require_consent()` in all 6 sub-pages | — | — |
| In-app consent states text goes to OpenAI | **Done** (2026-09-05) | [Home.py](../streamlit_app/Home.py) `_CONSENT_POINTS` | — | — |
| In-app consent states retention period | **Done** (2026-09-05) — 12 months, matching consent_form_vi.md §5 | same | — | — |
| "Delete my session" action | **Done** (2026-09-05) — `DELETE /session/{id}` across all 5 tables + two-step control on History | [api/main.py](../app/api/main.py), [6_History.py](../streamlit_app/pages/6_History.py) | — | — |
| Crisis-disclosing text not stored raw | **Done** (2026-09-05) — rule clears before any write on all 3 endpoints; nothing persisted on the crisis path | [services.py](../app/api/services.py), `TestCrisisDisclosuresAreNotRetained` | — | — |
| Automatic 12-month retention expiry | **Missing** — deletion is participant-initiated only | [api/main.py](../app/api/main.py) | S | M |
| Anonymous code shown at the point of result | **Missing** — only on History, so a participant who stops at Results cannot delete later | [5_Results.py](../streamlit_app/pages/5_Results.py) | S | M |
| Encryption at rest | **Missing** | plain SQLite, [database.py:29](../app/db/database.py#L29) | M | M |
| `GET /history/{id}` authorisation | **Missing** — unauthenticated, returns `raw_text` | [main.py:129-188](../app/api/main.py#L129-L188) | M | M |
| Data minimisation (age/gender/year/major/university) | **Partial** — collected and retained; stripped only on research export | [Home.py:99-107](../streamlit_app/Home.py#L99-L107) | S | M |
| Error details hidden from participants | **Broken** | `.streamlit/config.toml` → `showErrorDetails = true` | S | L |
| No secrets in repo or git history | **Done** — verified across all history | `.gitignore`, `git log --all -p` scan | — | — |
| `docs/ETHICS.md` (IRB-style, bias risks) | **Missing** | — | M | H |
| Consent form + participant instructions (offline) | **Done** (bracketed placeholders remain) | [consent_form_vi.md](consent_form_vi.md), [participant_instructions_vi.md](participant_instructions_vi.md) | S | M |

## 3. Data & experiments

| Feature | Status | Evidence | Effort | Impact |
|---|---|---|---|---|
| Synthetic dataset generator, seeded | **Done** | [research/generate_dataset.py](../research/generate_dataset.py); 500 rows × 75 cols | — | — |
| `stress_dataset_clean.csv` build script | **Missing** — the 500→466 transform is unreproducible | no script produces it | S | **H** |
| Frozen stratified split, reused by every system | **Done** | [research/baseline.py:39-55](../research/baseline.py#L39-L55); 326/70/70 | — | — |
| Exact-duplicate leakage check | **Done** (implicitly clean) | verified: 466 distinct texts, 0 crossing splits | — | — |
| Near-duplicate leakage check | **Done** (2026-09-09) — median 0.799, 34/70 above 0.80, under three measures, with the closest pairs printed verbatim *(was Missing)* | [scripts/check_leakage.py](../scripts/check_leakage.py), `data/eval/leakage.md` | — | — |
| `docs/DATA_CARD.md` (provenance, protocol, biases) | **Missing** | — | M | H |
| Data dictionary | **Done** (stale links) | [data/data_dictionary.md](../data/data_dictionary.md) | S | L |
| Baseline: majority class, 4-class harness | **Done** — macro-F1 0.1237, Cohen kappa 0.0 by definition *(was Missing)* | `data/eval/comparison.md` | — | — |
| Baseline: TF-IDF + LogReg | **Done** — acc 0.686 / macro-F1 0.682 | `data/eval/comparison.md` | — | — |
| Baseline: TF-IDF + SVM | **Done** — acc 0.657 / macro-F1 0.652 *(was Missing)* | `data/eval/comparison.md` | — | — |
| Baseline: fine-tuned PhoBERT | **Done** — acc 0.657 / macro-F1 0.533 (F1_severe = 0 by construction) | `data/eval/comparison.md` | — | — |
| Baseline: zero-shot LLM | **Done** (2026-09-08) — acc 0.529 / macro-F1 0.524 on `openai/gpt-oss-120b` via Groq, 0 parse failures at temperature 0 *(was Partial, never run)* | `data/eval/comparison.md` | — | — |
| Baseline: few-shot LLM (k=5) | **Missing** | — | S | M |
| Baseline: XLM-R / phobert-large | **Missing** | — | M | L |
| Proposed system (`llm_full`) evaluated | **Partial** — coded and tested, never run | [baselines.py:303-349](../app/eval/baselines.py#L303-L349) | **XS** | **H** |
| Ablation (5 configs) | **Partial** — harness done and tested, never run | [eval/ablation.py](../app/eval/ablation.py); `ablation.md` is a NOT-RUN marker | **XS** | **H** |
| Ablation: with/without segmentation | **Missing** | — | M | M |
| ≥3 seeds, mean ± std | **Missing** — every number is single-seed | — | M | H |
| Bootstrap 95 % CI | **Missing** | — | S | M |
| McNemar proposed-vs-best-baseline | **Missing** | — | S | M |
| RAG: Recall@k / MRR / nDCG | **Done** (2026-09-06) — 57 labelled queries; MRR 0.787, Recall@5 0.903 *(was Missing; this row contradicted section 5, which already recorded it as done)* | `data/eval/retrieval_eval.md` | — | — |
| RAG: faithfulness/groundedness judging | **Done** (2026-09-19) — 75 % of 121 suggestions fully supported, 99 % at least partially; no-RAG control declined on 39/40 items. Judge not yet human-validated *(was Missing)* | [faithfulness_eval.py](../app/eval/faithfulness_eval.py), RESULTS.md §4b | — | — |
| RAG: k-sweep, rerank ablation | **Missing** | — | M | M |
| LLM safety red-team suite (≥30 prompts) | **Missing** — the 50-item sets test the regex rule, not the LLM | `data/eval/crisis_testset.jsonl` | M | H |
| Crisis rule recall improved | **Done** (2026-09-09) — construct-based patterns replace the flat phrase list; on a held-out set frozen before the rewrite, P 0.600→**1.000**, R 0.200→**0.867**, indirect ideation 0/14→**11/14**, zero false positives across 20 idioms | [crisis_patterns.py](../app/nlp/crisis_patterns.py), `data/eval/crisis_eval_heldout.md` | — | — |
| Crisis rule measured in ENGLISH | **Done** (2026-09-09) — the app became English on 2026-09-05 while every published figure came from Vietnamese items; 50 new English items give P 1.000 / R 0.417 / F1 0.588, with 0 false positives across 16 lethal-sounding idioms and 0/10 on indirect ideation *(newly found gap)* | [crisis_testset_en.jsonl](../data/eval/crisis_testset_en.jsonl), `data/eval/crisis_eval_en.md` | — | — |
| Latency p50/p95, token/cost accounting | **Partial** (2026-09-08) — every deterministic stage and cold start measured exactly; the generation stage and token/cost need `--llm-samples` and provider quota *(was Missing)* | [eval/latency_eval.py](../app/eval/latency_eval.py), `data/eval/latency.md` | S | M |
| Real-data collection toolkit | **Done**, verified on the synthetic DB | [scripts/export_dataset.py](../scripts/export_dataset.py), [data_quality_report.py](../scripts/data_quality_report.py) | — | — |
| Real-data study run | **Missing** — no participants yet | [RESULTS.md](RESULTS.md) §5 | L | **H** |
| Human evaluation (accuracy/helpfulness/respect, Krippendorff α) | **Partial** — scaffolded and tested, no raters | [eval/export_for_rating.py](../app/eval/export_for_rating.py), [rating_analysis.py](../app/eval/rating_analysis.py) | M | H |
| SUS usability study | **Partial** — questionnaire + scorer ready, no participants | [sus_questionnaire_vi.md](sus_questionnaire_vi.md), [eval/sus_score.py](../app/eval/sus_score.py) | M | M |

## 4. Engineering & reproducibility

| Feature | Status | Evidence | Effort | Impact |
|---|---|---|---|---|
| Test suite | **Done** — **277 tests, all passing** (2026-09-08; was 198) | `python -m pytest tests/ -q` | — | — |
| Coverage on `app/` | **Done** — **93 % on the application code** (412 tests, measured 2026-09-24), 72 % once the offline evaluation scripts are included; services 95 %, scoring 100 %, safety gate 100 %, crisis patterns 100 %, retriever **76 %** (was 100 % before the pinned-chunk and embedding-mismatch paths were added; those are only partly exercised) | `pytest --cov=app` | — | — |
| Hand-computed scoring fixtures incl. edge cases | **Done** | [tests/test_scoring_dass21.py](../tests/test_scoring_dass21.py), [test_scoring_pss10.py](../tests/test_scoring_pss10.py) | — | — |
| API contract tests | **Done** — 14 tests | [tests/test_api.py](../tests/test_api.py) | — | — |
| RAG test with a fixed mini-corpus | **Done** | [tests/test_rag.py](../tests/test_rag.py), [test_retriever.py](../tests/test_retriever.py) (untracked) | — | — |
| CI (ruff + pytest, network-free) | **Done** | [.github/workflows/ci.yml](../.github/workflows/ci.yml) | — | — |
| Centralised config, no magic numbers in pages | **Done** | [app/config.py](../app/config.py) | — | — |
| `.env.example`, no committed secrets | **Done** | — | — | — |
| Pinned requirements | **Missing** — all 21 lines use `>=` | [requirements.txt](../requirements.txt) | **S** | M |
| Undeclared runtime deps (`sentence-transformers`, `tabulate`) | **Done** (2026-09-08) — both declared, each with the failure it prevents recorded inline *(was Broken)* | [requirements.txt](../requirements.txt) | — | — |
| Makefile targets | **Done** (POSIX make; Windows needs raw commands) | [Makefile](../Makefile) | S | L |
| Dockerfile + compose | **Partial** — never runs `app.rag.ingest`, so a fresh container has an empty KB and answers ungrounded | [Dockerfile](../Dockerfile), [docker-compose.yml](../docker-compose.yml) | S | M |
| Result artefacts under version control | **Missing** — `data/eval/*` is gitignored | [.gitignore](../.gitignore) | S | H |
| Evaluation uses the production retrieval path | **Done** (2026-09-08) — `_full_one` called its own query builder, diverging from `build_rag_query()` on 53 % of items; now shared, with a regression test *(newly found and fixed)* | [baselines.py](../app/eval/baselines.py), `TestEvalUsesProductionRetrieval` | — | — |
| Unparseable LLM replies retained for diagnosis | **Done** (2026-09-08) — failures were counted and then discarded; now written to `llm_cache/_parse_failures/` *(newly found and fixed)* | [baselines.py](../app/eval/baselines.py) | — | — |
| Report figures (4.2, 4.3, 4.6, 4.9) | **Done** (2026-09-08) — generated from artefacts on disk, so a figure cannot drift from the table beside it | [eval/make_figures.py](../app/eval/make_figures.py) | — | — |
| `results/`, `figures/`, `MANIFEST.json`, `experiments/run_all.py` | **Missing** | — | M | H |
| `docs/REPRODUCIBILITY.md` | **Missing** | — | S | M |
| Engineering decision log | **Done** — 207 lines, unusually thorough | [DECISIONS.md](../DECISIONS.md) | — | — |
| UI redesign committed | **Broken** — 814 changed lines + `ui/`, `static/`, `design-system/` untracked | `git status` | **XS** | M |

## 5. UI/UX

| Feature | Status | Evidence | Effort | Impact |
|---|---|---|---|---|
| 7-page Vietnamese flow, correct diacritics | **Done** | [streamlit_app/](../streamlit_app/) | — | — |
| Forward navigation blocked until consent | **Done** | `require_consent()` on every page | — | — |
| Progress indication | **Done** — sidebar step list + per-questionnaire progress bar | [ui/nav.py](../streamlit_app/ui/nav.py), `progress_bar` | — | — |
| Result page: band, sub-scores, plain-language explanation | **Done** — deliberately never leads with a number | [5_Results.py:45-72](../streamlit_app/pages/5_Results.py#L45-L72) | — | — |
| Retrieved sources shown for the advice | **Done** (2026-09-06) — advice is attributed to `cited_sources` (verified citations); `rag_sources` (searched) moved to an expander | [5_Results.py](../streamlit_app/pages/5_Results.py) | — | — |
| Grounding constraint in the prompt | **Done** (2026-09-06) — rule 4 forbids adding anything not in the retrieved material | [chain.py](../app/llm/chain.py) | — | — |
| Per-claim citations, verified | **Done** (2026-09-06) — `LlmAssessment.citations`; service discards ids not in the retrieved set | [services.py](../app/api/services.py) | — | — |
| Retrieval quality measured (Recall@k, MRR, nDCG) | **Done** (2026-09-06) — 57 labelled queries; MRR 0.787, Recall@5 0.903 | `data/eval/retrieval_eval.md` | — | — |
| Production query shape performs adequately | **Done** (2026-09-06) — rewritten to keep the student's sentence and drop the questionnaire label; MRR 0.509 → 0.839 on affected queries | `data/eval/retrieval_eval.md`, [services.py](../app/api/services.py) | — | — |
| Faithfulness measured (does the answer use the citation) | **Done** (2026-09-19) — LLM-as-judge (qwen3.8-27b, other family), no-RAG control arm; `--agreement` for judge-human kappa pending ratings *(was Missing)* | [faithfulness_eval.py](../app/eval/faithfulness_eval.py) | — | — |
| Colour never the sole carrier of meaning | **Done** | [ui/tokens.py:66-84](../streamlit_app/ui/tokens.py#L66-L84) | — | — |
| ≥4.5:1 contrast, measured not assumed | **Done** | [ui/tokens.py:20-24,42-45](../streamlit_app/ui/tokens.py#L20-L24) | — | — |
| Colour-blind-safe severity palette | **Partial** — green→amber→orange→red is a hue ramp; mitigated by mandatory text labels | [tokens.py:66-73](../streamlit_app/ui/tokens.py#L66-L73) | S | L |
| PDF export for the demo | **Missing** | grep: no PDF code anywhere | M | M |
| "Load sample session" (< 3-min demo) | **Missing** | — | S | M |
| Design-system documentation | **Done** (untracked) | [design-system/MASTER.md](../design-system/MASTER.md), [preview.py](../streamlit_app/preview.py) | — | — |
| Crisis state visually distinct and unmissable | **Done** | [utils.py:123-142](../streamlit_app/utils.py#L123-L142) | — | — |

---

## Summary counts

| Status | Count |
|---|---:|
| Done | 44 |
| Partial | 14 |
| Missing | 31 |
| Broken | 8 |

The eight **Broken** items — PSS-10 "official" claim, crisis recall, raw crisis text stored, ungrounded answers on retrieval failure, `showErrorDetails`, the missing clean-dataset script, undeclared runtime deps, and the uncommitted UI — are all **S**-effort except crisis recall. That is the cheapest block of grade recovery in the project.
