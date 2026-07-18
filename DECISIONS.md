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
