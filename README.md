# Academic Stress Detection System for Vietnamese University Students

An LLM-powered web application that estimates the academic stress level of
university students from (a) free-text input and (b) standardized
questionnaires (DASS-21, PSS-10), and returns an explainable assessment with
RAG-grounded coping suggestions. The interface is English; the free-text
analysis accepts English and Vietnamese.

> ⚠️ **This is a screening/self-reflection aid, NOT a diagnostic tool.** Every
> result screen shows this disclaimer, and a deterministic crisis-detection
> rule surfaces Vietnamese mental-health helplines instead of a normal
> assessment when self-harm risk is indicated.

## Architecture

```
Streamlit UI (English, multipage)             FastAPI backend
┌───────────────────────────────┐   HTTP    ┌──────────────────────────────────┐
│ 1. Home / consent             │ ────────▶ │ POST /assess/text                │
│ 2. Share how you feel (text)  │           │ POST /assess/questionnaire       │
│ 3. DASS-21   4. PSS-10        │           │ POST /assess/full                │
│ 5. Academic context           │           │ GET  /history/{student_id}       │
│ 6. Results   7. History       │           │ DEL  /session/{student_id}       │
│                               │           │ GET  /health                     │
└───────────────────────────────┘           └───────┬──────────────────────────┘
                                                    │
        ┌───────────────┬───────────────┬───────────┼───────────────┐
        ▼               ▼               ▼           ▼               ▼
  Crisis rule     Scoring engines   NLP (PhoBERT   ChromaDB RAG   LangChain +
  (deterministic  (DASS-21/PSS-10,  stress clf +   (English       LLM provider
  gate: runs      ground truth)     bilingual      knowledge      (structured
  before any side                   lexicon)       base)          JSON output)
  effect)
                                        └──────── SQLite via SQLAlchemy ───────┘
```

The pipeline for `POST /assess/full`:

1. **NLP** — fine-tuned local PhoBERT stress classifier + a bilingual
   stress-keyword lexicon; sentiment polarity is derived from these two signals
   (no separate sentiment model, fully offline; degrades to lexicon-only if the
   classifier is unavailable). PhoBERT is Vietnamese-only, so it is consulted
   only for Vietnamese input; English text is scored by the lexicon alone.
2. **Deterministic scoring** — official DASS-21 and PSS-10 scoring rules produce
   the ground-truth label (`Low/Moderate/High/Severe`).
3. **Crisis rule** — runs *before* any LLM call; on self-harm signals the flow
   bypasses the LLM and returns helpline information.
4. **RAG** — top-k retrieval from a curated knowledge base (ChromaDB,
   multilingual sentence-transformer embeddings). Retrieval quality is measured;
   see [docs/RESULTS.md](docs/RESULTS.md) §4b.
5. **LLM** — a LangChain chain returns structured JSON: predicted level,
   confidence, reasoning, 3 actionable suggestions, risk flags and citations.
   Suggestions may not go beyond the retrieved material, citations are verified
   against what was actually retrieved, and an empty retrieval means no advice
   is generated at all. If the LLM fails, deterministic results are still
   returned.
6. **Persistence** — every artifact is stored under an anonymized UUID; no
   personally identifying fields are ever sent to the language-model provider.
   Crisis disclosures are never persisted.

## Setup

Requirements: Python 3.11+ (developed on 3.13), ~4 GB disk for models.

```bash
pip install -r requirements.txt
cp .env.example .env          # then set OPENAI_API_KEY (any OpenAI-compatible
                              # provider works, see docs/RUNNING_LLM_EVAL.md)
```

Optional but recommended — the local fine-tuned PhoBERT stress classifier is
expected at `models/phobert-stress` (see `research/phobert_finetune.py` to
reproduce it). Without it the app degrades to lexicon-only text analysis.

### Seed the knowledge base and synthetic data

```bash
python scripts/seed.py --rows 200      # ChromaDB ingestion + 200 synthetic students
# or: make seed
```

First run downloads the multilingual embedding model (~500 MB) once.

### Run

```bash
# Terminal 1 — API (docs at http://127.0.0.1:8000/docs)
uvicorn app.api.main:app --port 8000

# Terminal 2 — UI (http://localhost:8501)
streamlit run streamlit_app/Home.py
```

Or with Docker:

```bash
docker compose up --build     # API on :8000, UI on :8501
```

### Tests

```bash
python -m pytest tests/ -q
```

The suite covers the scoring engines (official cutoff boundary tests), the
lexicon/NLP module (models mocked), RAG chunking + retrieval (real ChromaDB on
a temp dir), the LangChain chain (fake LLM), the crisis rules, and all API
endpoints (TestClient with mocked NLP/RAG/LLM). No network or API key needed.

### Evaluation

```bash
python -m app.eval.synthetic --rows 200   # if not already seeded
python -m app.eval.evaluate               # accuracy, macro-F1, Cohen's kappa
```

Writes `data/eval/metrics.json` and `data/eval/confusion_matrix.png` comparing
`llm_predicted_label` against the questionnaire-derived `ground_truth_label`.

## Reproducing the experiments

All experiment artifacts land in `data/eval/`; computed tables are collected in
[docs/RESULTS.md](docs/RESULTS.md). Numbers based on synthetic data are labeled
as such in every output. Commands, in the order a fresh clone would run them:

```bash
# 0. One-time setup
pip install -r requirements.txt
cp .env.example .env               # set OPENAI_API_KEY for the LLM systems
#    Any OpenAI-compatible provider works via OPENAI_BASE_URL (Groq,
#    OpenRouter, Gemini, local Ollama). Step-by-step: docs/RUNNING_LLM_EVAL.md
python scripts/seed.py --rows 200  # ChromaDB ingestion + synthetic DB rows

python scripts/check_llm.py        # pre-flight the LLM provider before spending quota

# 1. Baseline comparison (tfidf_lr, phobert_ft, llm_zeroshot, llm_full)
#    Same frozen stratified split for every system; LLM responses are cached
#    under data/eval/llm_cache/ so re-runs are free and deterministic.
python -m app.eval.compare --dataset synthetic
#    -> data/eval/comparison.csv, comparison.md, confusion_<system>.png
#    LLM systems are skipped with an explicit note if no valid key is set.

# 2. Ablation study (full / no_rag / no_questionnaire / no_emotion / text_only)
python -m app.eval.ablation --dataset synthetic
#    -> data/eval/ablation.csv, ablation.md, ablation.png   (requires API key)

# 3. Crisis-rule evaluation (50 hand-labeled Vietnamese items; offline)
python -m app.eval.crisis_eval
#    -> data/eval/crisis_eval.md  (precision/recall/F1 + every FP/FN verbatim)

# 4. Retrieval-quality evaluation (57 hand-labeled queries; offline)
python -m app.eval.retrieval_eval
#    -> data/eval/retrieval_eval.md  (Recall@k / MRR / nDCG@k, k sweep,
#       breakdown by query shape, and every miss verbatim)

# 5. Real-data study, once participants have used the app
python scripts/export_dataset.py --split      # SQLite -> data/real/dataset.csv
python scripts/data_quality_report.py         # flag suspect submissions
python -m app.eval.compare --dataset real     # identical pipeline, real data

# 6. Human evaluation
python -m app.eval.export_for_rating --n 30 --raters 3   # blank rating sheets
python -m app.eval.rating_analysis --dir data/eval/rating # after sheets return
python -m app.eval.sus_score --csv <sus_responses.csv>    # SUS usability score
```

Determinism notes: every script takes `--seed` (default 42) where randomness
exists; the train/test split is frozen in `data/stress_dataset_split.csv`
(reused so PhoBERT's fine-tuning train set never leaks into test); LLM calls
run at temperature 0 for `llm_zeroshot` and are disk-cached for all systems.

## Report and slides

The submitted report lives in [`report/latex/`](report/latex/) — `main.tex`
plus `chapters/*.tex`, in the HCMIU template. Build it with pdfLaTeX:

```powershell
cd report/latex
.\build.ps1                     # -> main.pdf, 75 pages, about 12 s
```

Every figure in it is generated rather than drawn, so a changed result cannot
leave a stale picture behind:

```bash
python report/make_report_figures.py   # 13 charts, read from data/eval/
python report/render_diagrams.py       # 12 Mermaid diagrams (Playwright)
python report/capture_screenshots.py   # 5 UI screenshots (needs the app running)
python report/build_slides.py          # the defence deck
```

The build PDF is not tracked; `docs/RESULTS.md` and `data/eval/` are the
authoritative numbers. An earlier Markdown-sourced version of the report is in
[`report/archive/`](report/archive/) and is **not current** — see the README
there before reading anything in it.

## Repository layout

```
app/
  config.py         pydantic-settings configuration (.env)
  scoring/          DASS-21 & PSS-10 engines + unified ground-truth label
  nlp/              emotion.py (PhoBERT stress clf), lexicon.py (VN keywords)
  rag/              ChromaDB store, Markdown ingestion, retriever
  llm/              chain.py (LangChain + Pydantic parser), safety.py (crisis rule)
  api/              FastAPI app (main.py) + orchestration (services.py)
  db/               SQLAlchemy models + session management
  eval/             synthetic data generator + agreement metrics
streamlit_app/      multipage Vietnamese UI (consent → input → results → history)
data/knowledge/     Vietnamese Markdown knowledge base for RAG
research/           pre-existing thesis research scripts (dataset generation,
                    TF-IDF baselines, PhoBERT fine-tuning)
tests/              pytest suite
```

## Safety design

- **Non-diagnostic disclaimer** on every result surface (API responses carry
  `disclaimer`; every UI page renders it).
- **Crisis detection** is deterministic and runs before the LLM: explicit
  self-harm phrases in text (English and Vietnamese), or DASS-21 risk items (17, 21) at
  maximum, or Extremely Severe depression with an elevated risk item, all
  bypass the normal output and show helplines (Ngày Mai 096 306 1414, 111, 115).
- **Crisis disclosures are not retained.** The rule runs before any write, so a
  self-harm disclosure is routed to helplines and never persisted. Only the
  trigger reasons are logged, never the text.
- **The validated instrument decides the headline.** When a DASS-21 / PSS-10
  score exists it is what the results page reports; the LLM supplies explanation
  and suggestions only. Disagreement between the two is shown to the student,
  and its rate is reported by `app/eval/evaluate.py`.
- **Right to withdraw**: `DELETE /session/{student_id}` erases every row for an
  anonymized id, exposed as a two-step control on the History page.
- **Consent gate** before any data entry; only anonymized UUIDs are stored. The
  in-app consent states third-party processing (the provider is named at runtime from the configured endpoint — currently Groq), the retention period,
  and the right to erase.
- **Privacy**: the LLM prompt contains the free text, scores, and non-identifying
  context only — never IDs or demographic identifiers.

## License / academic context

Pre-thesis project. Questionnaire instruments (DASS-21, PSS-10) are used under
their respective research-use terms; Vietnamese DASS-21 wording follows the
validated adaptation (Tran et al., 2013) with minor smoothing.
