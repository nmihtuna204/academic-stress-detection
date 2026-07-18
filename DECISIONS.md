# Engineering Decisions

Running log of non-obvious defaults chosen without blocking on the user.

## Phase 1 — scaffold, DB, scoring

- **Pre-existing research code preserved, not deleted.** The repo already contained
  a synthetic-dataset generator, TF-IDF baselines, and a fine-tuned PhoBERT stress
  classifier (`models/phobert-stress`, 3-class Low/Moderate/High). These moved to
  `research/` (with `app/dass21.py` → `research/dass21_original.py` and the English
  emotion module → `research/emotion_en.py`). The application in `app/` is built to
  the project brief; the fine-tuned PhoBERT model is reused as the primary local
  stress signal in `app/nlp/` (see Phase 2).
- **Python environment**: packages install into the user site-packages (no venv),
  matching how the existing torch/transformers stack was already installed.
  Python 3.13.
- **DASS-21 scoring** reuses the previously written, already-correct implementation
  (official Lovibond cutoffs on doubled sums), extended with validated-style
  Vietnamese item wording (`text_vi`) for the UI.
- **PSS-10 cutoffs**: Cohen's conventional 0–13 Low / 14–26 Moderate / 27–40 High.
- **Unified ground-truth label** (`Low/Moderate/High/Severe`) = the more severe of
  - DASS-21 *stress subscale*: Normal→Low, Mild/Moderate→Moderate, Severe→High,
    Extremely Severe→Severe, and
  - PSS-10: Low→Low, Moderate→Moderate, High→High.
  Rationale: both instruments are stress screens; taking the max is conservative
  (screening context favors sensitivity over specificity).
- **Questionnaire table**: one row may hold DASS-21 only, PSS-10 only, or both —
  all item columns nullable; derived scores only set for the part submitted.
- **IDs**: all primary keys are UUID4 strings generated app-side (anonymized;
  no real student numbers anywhere).
- **Timestamps** stored as naive UTC datetimes in SQLite.

## Phase 2 — NLP

- **Two-model strategy**: primary signal is the locally fine-tuned
  `models/phobert-stress` (3-class stress). Sentiment polarity comes from
  `wonrax/phobert-base-vietnamese-sentiment` (POS/NEG/NEU) when downloadable;
  if neither model is available the module degrades to lexicon-only analysis
  (keyword matching still works offline) rather than crashing.
- **Language detection** is heuristic (Vietnamese diacritics + stopword ratio),
  no external dependency.

## Phase 3 — RAG

- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers,
  local) because the corpus and queries are Vietnamese; falls back to Chroma's
  default ONNX MiniLM if unavailable. Cosine HNSW space.
- **Chunking**: split on `##` headings with the document title prepended to every
  chunk; oversize sections re-split on paragraph boundaries (~1500 chars max).
  Deterministic chunk ids make ingestion idempotent.
- **Knowledge base**: 6 curated Vietnamese Markdown docs written for this project
  (stress overview, coping strategies, VN support resources, sleep, the DASS/PSS
  instruments, family/financial pressure). Helpline numbers are the publicly
  listed ones (Ngày Mai 096 306 1414, national 111, emergency 115).

## Phase 4 — LLM chain

- **Structured output** via `PydanticOutputParser` (per brief) in an LCEL chain
  `prompt | llm | parser`; tests inject `FakeMessagesListChatModel`.
- **Default model** `gpt-4o-mini` (configurable via `OPENAI_MODEL`) — cheap and
  sufficient for guided assessment with rich evidence in the prompt.
- **Crisis rule triggers** (deterministic, pre-LLM): explicit Vietnamese
  self-harm phrases; DASS items 17 & 21 both = 3; or Extremely Severe depression
  with either risk item ≥ 2. Conservative keyword list to limit false positives.

## Phase 5 — API

- `/assess/text` and `/assess/questionnaire` are deterministic (no LLM, no RAG)
  so the core screening loop works without an OpenAI key. Only `/assess/full`
  invokes RAG + LLM, and it degrades to deterministic results if the LLM errors.
- Users are auto-created on first assessment; passing a known `student_id` links
  new entries to the same anonymized history.

## Phase 6 — UI

- Page files use unaccented names (Windows-safe); all visible text is Vietnamese.
- Stress levels use status colors (green/amber/orange/red) always paired with the
  Vietnamese text label — color never carries meaning alone.
- The crisis path hides all analysis output and shows only the helpline block.

## Phase 7 — eval & packaging

- Synthetic generator drives all instruments from a latent stress θ per student
  (internally consistent answers) and simulates an LLM with ~72% agreement,
  erring only to adjacent classes — mirrors expected real behavior.
- Docker image installs CPU-only torch to keep size manageable; one shared image
  for API and UI services; models/ mounted read-only (not baked into the image).
- `models/`, DB, Chroma dir, and eval artifacts are gitignored (large/derived).

## Defense-strengthening — Phase 1 (baseline comparison)

- **The train/val/test split is reused from `research/baseline.py`** (frozen in
  `data/stress_dataset_split.csv`, seed 42, stratified) instead of being redrawn:
  `models/phobert-stress` was fine-tuned on that split's train portion, so any new
  split would leak fine-tuning data into the test set and inflate `phobert_ft`.
  The stratification was done on the original 3-class label; the derived 4-class
  distribution over the 70-row test set is Low 16 / Moderate 23 / High 22 /
  Severe 9 (computed; the exact dataframe is written to
  `data/eval/dataset_synthetic.csv` on every run).
- **PhoBERT 3→4 class mapping is the identity** on {Low, Moderate, High}; the
  model simply cannot predict Severe (F1_severe = 0 by construction). Any
  score-threshold remapping to synthesize a Severe class would be arbitrary, so
  the limitation is reported instead of patched.
- **Honest result (synthetic data)**: `tfidf_lr` (acc 0.686, macro-F1 0.682)
  currently BEATS `phobert_ft` (acc 0.657, macro-F1 0.533) on the 4-class task,
  chiefly because of the missing Severe class. The LLM systems have not produced
  numbers yet: the configured `OPENAI_API_KEY` is the placeholder value, and no
  metric is written down that was not actually computed. Once a key is set,
  `python -m app.eval.compare --dataset synthetic` fills in both LLM rows from
  the same frozen split (responses disk-cached under `data/eval/llm_cache/`).
- **Known validity caveat, stated wherever results appear**: `llm_full` receives
  the DASS/PSS scores from which the ground-truth label is derived, so its
  agreement is partly by construction. The `no_questionnaire` ablation is the
  honest text-only comparison point.
- LLM eval calls default to `HF_HUB_OFFLINE=1` (local/cached HF models only) so a
  slow hub connection cannot hang an evaluation; `--online-hub` opts out.

## Defense-strengthening — Phase 2 (ablation)

- The ablation reuses the exact `run_llm_full` engine from the baseline
  comparison with three feature switches (RAG / questionnaire / emotion), so an
  ablation config and the headline system can never drift apart.
- The interpretation paragraph in `data/eval/ablation.md` is **generated from the
  computed deltas**, never hand-written, and always restates the questionnaire
  label-leakage caveat (the `no_questionnaire` delta measures leakage as much as
  feature value).
- With no valid OpenAI key the runner writes an explicit "NOT RUN" marker file
  instead of empty or invented tables.

## Defense-strengthening — Phase 3 (crisis-rule evaluation)

- Built a 50-item hand-labeled Vietnamese test set (`data/eval/crisis_testset.jsonl`,
  explicitly un-gitignored — it is source data): 20 true positives (explicit +
  indirect ideation), 20 hard negatives (hyperbole like "mệt muốn chết", reported
  speech), 10 borderline items each carrying the annotation rationale in a `note`.
  Borderline labeling policy: passive death wish / ideation mention → true;
  hopelessness or burdensomeness without any death reference → false for the
  *bypass* rule (they deserve a soft risk flag, not result suppression).
- **Measured (not tuned): precision 0.800, recall 0.500, F1 0.615.**
  Remaining failure modes, reported as they landed:
  - The substring rule fires on "muốn chết" inside hyperbole/reported speech
    (3 FP: items 23, 24, 40) — no negation/context handling.
  - Indirect ideation is almost entirely missed (8/9 indirect_tp are FN):
    means-referencing plans ("uống thật nhiều thuốc ngủ"), farewell-letter
    references, burdensomeness with a death reference, passive ideation.
    Explicit phrasing is caught 10/10; the DASS-item triggers behave as designed.
- Per instructions the rule was NOT modified to fit this set; the set is the
  measurement instrument. The FN list doubles as the roadmap if the rule is
  revised later (any revision must be evaluated on a NEW held-out set).

## Defense-strengthening — Phase 4 (data-collection toolkit)

- **Admin access is CLI-only** (`scripts/export_dataset.py`, `scripts/
  data_quality_report.py`), not a Streamlit admin page: the participant-facing
  app must not ship a data-export surface, and the researcher runs on the host
  where the DB lives anyway.
- **Export strips demographics** (age/gender/year/major/university) even though
  they are only quasi-identifying — the eval pipeline doesn't use them, so the
  analysis CSV carries the minimum: UUID, text, items, derived scores/labels.
  `data/real/` is inside the gitignored data dirs; real data never enters git.
- Export takes the LATEST text entry and LATEST scored questionnaire per student
  (repeat participants contribute one row) and skips students with no scored
  questionnaire (no ground truth derivable).
- Quality flags are advisory (straight-lining, <20-word text, <120s completion,
  DASS/PSS ≥2 unified levels apart); exclusions must be manual and documented.
  Verified live on the synthetic DB: 201/201 flagged for missing text + instant
  completion (correct - synthetic rows have neither), plus 2 real mismatch flags.
- Consent form and participant instructions carry bracketed placeholders for
  researcher name/contact - to be filled before any real collection; the crisis
  procedure section mirrors exactly what the app does.
