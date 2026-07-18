# Academic Stress Detection System for Vietnamese University Students

An LLM-powered web application that estimates the academic stress level of
Vietnamese university students from (a) free-text input in Vietnamese and
(b) standardized questionnaires (DASS-21, PSS-10), and returns an explainable
assessment with RAG-grounded coping suggestions.

> ⚠️ **This is a screening/self-reflection aid, NOT a diagnostic tool.** Every
> result screen shows this disclaimer in Vietnamese, and a deterministic
> crisis-detection rule surfaces Vietnamese mental-health helplines instead of
> a normal assessment when self-harm risk is indicated.

## Architecture

```
Streamlit UI (Vietnamese, multipage)          FastAPI backend
┌───────────────────────────────┐   HTTP    ┌──────────────────────────────────┐
│ 1. Trang chủ / consent        │ ────────▶ │ POST /assess/text                │
│ 2. Nhập cảm nghĩ (free text)  │           │ POST /assess/questionnaire       │
│ 3. DASS-21   4. PSS-10        │           │ POST /assess/full                │
│ 5. Bối cảnh & nguồn lực       │           │ GET  /history/{student_id}       │
│ 6. Kết quả   7. Lịch sử       │           │ GET  /health                     │
└───────────────────────────────┘           └───────┬──────────────────────────┘
                                                    │
        ┌───────────────┬───────────────┬───────────┼───────────────┐
        ▼               ▼               ▼           ▼               ▼
  Crisis rule     Scoring engines   NLP (PhoBERT   ChromaDB RAG   LangChain +
  (deterministic, (DASS-21/PSS-10,  stress + VN    (Vietnamese    OpenAI
  runs first)     ground truth)     sentiment +    knowledge      (structured
                                    lexicon)       base)          JSON output)
                                        └──────── SQLite via SQLAlchemy ───────┘
```

The pipeline for `POST /assess/full`:

1. **NLP** — fine-tuned local PhoBERT stress classifier + Vietnamese sentiment
   model + a ~90-term Vietnamese stress-keyword lexicon (each layer degrades
   gracefully if a model is unavailable).
2. **Deterministic scoring** — official DASS-21 and PSS-10 scoring rules produce
   the ground-truth label (`Low/Moderate/High/Severe`).
3. **Crisis rule** — runs *before* any LLM call; on self-harm signals the flow
   bypasses the LLM and returns helpline information.
4. **RAG** — top-k retrieval from a curated Vietnamese knowledge base
   (ChromaDB, multilingual sentence-transformer embeddings).
5. **LLM** — a LangChain chain (OpenAI) returns structured JSON: predicted
   level, confidence, Vietnamese reasoning, 3 actionable suggestions, risk
   flags. If the LLM fails, deterministic results are still returned.
6. **Persistence** — every artifact is stored under an anonymized UUID; no
   personally identifying fields are ever sent to the OpenAI API.

## Setup

Requirements: Python 3.11+ (developed on 3.13), ~4 GB disk for models.

```bash
pip install -r requirements.txt
cp .env.example .env          # then set OPENAI_API_KEY
```

Optional but recommended — the local fine-tuned PhoBERT stress classifier is
expected at `models/phobert-stress` (see `research/phobert_finetune.py` to
reproduce it). Without it the app falls back to the HF sentiment model and the
keyword lexicon.

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
streamlit run streamlit_app/Trang_Chu.py
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

## Repository layout

```
app/
  config.py         pydantic-settings configuration (.env)
  scoring/          DASS-21 & PSS-10 engines + unified ground-truth label
  nlp/              emotion.py (PhoBERT + sentiment), lexicon.py (VN keywords)
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
  `disclaimer_vi`; every UI page renders it).
- **Crisis detection** is deterministic and runs before the LLM: explicit
  Vietnamese self-harm phrases in text, or DASS-21 risk items (17, 21) at
  maximum, or Extremely Severe depression with an elevated risk item, all
  bypass the normal output and show helplines (Ngày Mai 096 306 1414, 111, 115).
- **Consent gate** before any data entry; only anonymized UUIDs are stored.
- **Privacy**: the LLM prompt contains the free text, scores, and non-identifying
  context only — never IDs or demographic identifiers.

## License / academic context

Pre-thesis project. Questionnaire instruments (DASS-21, PSS-10) are used under
their respective research-use terms; Vietnamese DASS-21 wording follows the
validated adaptation (Tran et al., 2013) with minor smoothing.
