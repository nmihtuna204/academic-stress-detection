# Project Structure

Generated from the actual source: line counts are non-blank lines, and every edge in the dependency graphs below is a real `import` statement extracted by AST parsing — not a description of intent.

> **Preview note.** GitHub renders these diagrams natively. In VS Code, the built-in Markdown preview needs the *Markdown Preview Mermaid Support* extension; without it the diagrams show as code blocks.

**Total: 7,956 lines across 78 Python files.**

| Package | Lines | Share | Role |
|---|---:|---:|---|
| `app/` | 3,034 | 38 % | Backend: scoring, NLP, LLM, RAG, API, persistence, evaluation |
| `streamlit_app/` | 2,397 | 30 % | Vietnamese frontend + internal design system |
| `tests/` | 1,399 | 18 % | 198 tests, 83 % coverage of `app/` |
| `research/` | 855 | 11 % | Frozen: dataset generation, splits, fine-tuning |
| `scripts/` | 271 | 3 % | Operational: seeding, export, quality reporting |

---

## 1. Repository map

```mermaid
graph TD
    ROOT["Pre-Thesis/"]

    ROOT --> APP["app/ — 3,034<br/>backend"]
    ROOT --> UI["streamlit_app/ — 2,397<br/>frontend"]
    ROOT --> TEST["tests/ — 1,399<br/>198 tests"]
    ROOT --> RES["research/ — 855<br/>frozen experiments"]
    ROOT --> SCR["scripts/ — 271<br/>operations"]
    ROOT --> DATA["data/<br/>corpora + stores"]
    ROOT --> DOCS["docs/ + report/<br/>audit + thesis"]

    APP --> A1["scoring/ — 267<br/>DASS-21, PSS-10"]
    APP --> A2["nlp/ — 235<br/>PhoBERT + lexicon"]
    APP --> A3["llm/ — 237<br/>chain + safety"]
    APP --> A4["rag/ — 185<br/>ingest, store, retrieve"]
    APP --> A5["api/ — 371<br/>5 endpoints"]
    APP --> A6["db/ — 186<br/>5 tables"]
    APP --> A7["schemas/ — 233<br/>Pydantic contracts"]
    APP --> A8["eval/ — 1,279<br/>baselines, ablation, crisis"]
    APP --> A9["config.py — 39"]

    UI --> U1["Home.py — 115<br/>consent gate"]
    UI --> U2["pages/ — 819<br/>6 pages"]
    UI --> U3["ui/ — 1,193<br/>design system"]
    UI --> U4["utils.py — 117<br/>session + API client"]

    DATA --> D1["knowledge/ — 6 docs<br/>→ 23 chunks"]
    DATA --> D2["chroma/ — vector store"]
    DATA --> D3["eval/ — results"]
    DATA --> D4["*.csv — 466 records"]

    classDef core fill:#e8f0fe,stroke:#3b6ea5,stroke-width:2px
    classDef safe fill:#fde8e8,stroke:#c53030,stroke-width:2px
    class A1,A5 core
    class A3 safe
```

---

## 2. Backend module dependencies

Every arrow is a real import. Note the shape: `scoring/`, `schemas/`, `config` and `nlp/lexicon` are leaves that depend on nothing internal — which is why they are the most testable parts of the system.

```mermaid
graph BT
    subgraph L0["Layer 0 — no internal dependencies"]
        CFG["config.py"]
        DASS["scoring/dass21.py<br/>135"]
        PSS["scoring/pss10.py<br/>82"]
        ENUM["schemas/enums.py<br/>33"]
        LEX["nlp/lexicon.py<br/>92"]
        DBM["db/models.py<br/>123"]
    end

    subgraph L1["Layer 1 — primitives"]
        SCORE["scoring/__init__.py<br/>derive_ground_truth"]
        SCHEMA["schemas/models.py<br/>151"]
        STORE["rag/store.py<br/>50"]
        DBASE["db/database.py<br/>42"]
    end

    subgraph L2["Layer 2 — services"]
        EMO["nlp/emotion.py<br/>133"]
        SAFE["llm/safety.py — 66<br/>CRISIS RULE"]
        RETR["rag/retriever.py<br/>41"]
        INGEST["rag/ingest.py<br/>90"]
    end

    subgraph L3["Layer 3 — orchestration"]
        CHAIN["llm/chain.py<br/>167"]
        SVC["api/services.py<br/>208"]
    end

    subgraph L4["Layer 4 — entry point"]
        MAIN["api/main.py — 162<br/>5 endpoints"]
    end

    DASS --> SCORE
    PSS --> SCORE
    ENUM --> SCHEMA
    CFG --> STORE
    CFG --> DBASE
    DBM --> DBASE

    LEX --> EMO
    ENUM --> EMO
    SCHEMA --> EMO
    CFG --> EMO
    LEX --> SAFE
    DASS --> SAFE
    STORE --> RETR
    STORE --> INGEST
    CFG --> INGEST

    RETR --> CHAIN
    SCHEMA --> CHAIN
    CFG --> CHAIN

    SCORE --> SVC
    EMO --> SVC
    SAFE --> SVC
    RETR --> SVC
    CHAIN --> SVC
    SCHEMA --> SVC
    DBM --> SVC

    SVC --> MAIN
    SAFE --> MAIN
    EMO --> MAIN
    RETR --> MAIN
    DBASE --> MAIN
    SCHEMA --> MAIN

    classDef safety fill:#fde8e8,stroke:#c53030,stroke-width:3px
    classDef truth fill:#e6f4ea,stroke:#2d7a4d,stroke-width:2px
    class SAFE safety
    class DASS,PSS,SCORE truth
```

**Why the layering matters.** `llm/safety.py` (red) sits at Layer 2 and imports only the lexicon and the DASS item definitions — no network, no model, no database. That is what makes the crisis rule deterministic and testable in isolation. `scoring/` (green) is the ground-truth source and has zero internal dependencies.

---

## 3. Frontend structure

```mermaid
graph TD
    HOME["Home.py — 115<br/>consent gate"]

    HOME --> P1["1_Share_Feelings — 75<br/>free text"]
    P1 --> P2["2_DASS_21 — 69"]
    P2 --> P3["3_PSS_10 — 63"]
    P3 --> P4["4_Context — 134<br/>context"]
    P4 --> P5["5_Results — 328<br/>results"]
    P5 --> P6["6_History — 150<br/>history"]

    subgraph DS["ui/ — internal design system, 1,193"]
        THEME["theme.py — 438<br/>CSS + palette"]
        COMP["components.py — 295<br/>cards, callouts, heroes"]
        CHART["charts.py — 188<br/>gauge, radar, bars"]
        ICON["icons.py — 135<br/>inline SVG"]
        TOK["tokens.py — 84<br/>spacing, colour"]
        NAV["nav.py — 45<br/>stepper"]
    end

    UTIL["utils.py — 117<br/>session state + HTTP client"]

    P1 & P2 & P3 & P4 & P5 & P6 --> UTIL
    P1 & P2 & P3 & P4 & P5 & P6 --> COMP
    P5 & P6 --> CHART
    COMP --> ICON
    NAV --> ICON
    TOK --> THEME
    TOK --> COMP

    P2 -.->|"imports scoring<br/>directly"| SC["app/scoring/dass21"]
    P3 -.->|"imports scoring<br/>directly"| SC2["app/scoring/pss10"]

    classDef gate fill:#fff4e5,stroke:#b26b00,stroke-width:2px
    class HOME gate
```

The dotted edges are worth noting: pages 2 and 3 import the scoring package directly to render item text and response labels, so the questionnaire wording has exactly one source of truth shared with the backend.

---

## 4. Request flow — `POST /assess/full`

```mermaid
sequenceDiagram
    autonumber
    participant P5 as 5_Results.py
    participant API as api/main.py
    participant SVC as api/services.py
    participant NLP as nlp/emotion.py
    participant SC as scoring/
    participant CR as llm/safety.py
    participant RG as rag/retriever.py
    participant CH as llm/chain.py
    participant DB as db/

    P5->>API: FullAssessmentRequest
    API->>SVC: run_full_assessment()
    SVC->>NLP: analyze(text)
    NLP-->>SVC: label, confidence, keywords
    SVC->>SC: score_dass21 / score_pss10
    SC-->>SVC: subscales + derive_ground_truth()
    SVC->>CR: check_crisis(text, answers, severity)

    alt Crisis triggered
        CR-->>SVC: is_crisis = true
        Note over SVC,CH: retrieval and LLM never invoked
        SVC-->>P5: helplines only
    else Normal
        SVC->>RG: retrieve(query, k=4)
        RG-->>SVC: 4 chunks
        SVC->>CH: assess(evidence + chunks)
        CH-->>SVC: structured JSON
        Note over SVC: on failure → deterministic result
        SVC->>DB: persist under UUID
        SVC-->>P5: level, reasoning, 3 suggestions, sources
    end
```

---

## 5. Data and artifact flow

```mermaid
graph LR
    subgraph GEN["Generation — frozen, seed 42"]
        G1["research/generate_dataset.py<br/>357 lines · 41 templates"]
        G1 --> C1["stress_dataset.csv<br/>500 rows"]
        C1 --> C2["stress_dataset_clean.csv<br/>466 unique"]
        C2 --> G2["research/baseline.py<br/>stratified split"]
        G2 --> C3["stress_dataset_split.csv<br/>326 / 70 / 70"]
    end

    subgraph TRAIN["Training"]
        C3 --> T1["research/phobert_finetune.py"]
        T1 --> M1[("models/phobert-stress<br/>3 classes")]
    end

    subgraph KB["Knowledge base"]
        K1["data/knowledge/<br/>6 Vietnamese docs"]
        K1 --> K2["rag/ingest.py<br/>split on H2"]
        K2 --> K3[("chroma/<br/>23 chunks")]
    end

    subgraph EVAL["Evaluation"]
        C3 --> E1["eval/datasets.py<br/>→ 4-class labels"]
        E1 --> E2["eval/baselines.py<br/>TF-IDF · PhoBERT · LLM"]
        M1 --> E2
        K3 --> E2
        E2 --> E3["eval/compare.py"]
        E2 --> E4["eval/ablation.py<br/>5 configs"]
        E3 --> R1["data/eval/*.json, *.md, *.png"]
        E4 --> R1
    end

    subgraph SAFETY["Safety evaluation"]
        S1["crisis_testset.jsonl<br/>50 hand-labelled"]
        S1 --> S2["eval/crisis_eval.py"]
        S2 --> R2["crisis_eval.md<br/>P .800 R .500"]
    end

    R1 --> RPT["report/PreThesis_Report.md"]
    R2 --> RPT

    classDef stale fill:#fff4e5,stroke:#b26b00,stroke-dasharray:4 3
    class C2 stale
```

> ⚠️ `stress_dataset_clean.csv` (amber) is consumed by the split script but produced by a step **no longer present in the repository** — a reproducibility defect recorded in the report's Appendix D.

---

## 6. Test coverage map

```mermaid
graph LR
    subgraph T["tests/ — 1,399 lines, 198 tests"]
        T1["test_scoring_dass21 — 93"]
        T2["test_scoring_pss10 — 74"]
        T3["test_ground_truth — 29"]
        T4["test_llm — 151"]
        T5["test_nlp — 104"]
        T6["test_rag — 62"]
        T7["test_retriever — 80"]
        T8["test_api — 132"]
        T9["test_db_models — 57"]
        T10["test_eval_comparison — 129"]
        T11["test_ablation — 73"]
        T12["test_crisis_eval — 74"]
        T13["test_human_eval — 138"]
        T14["test_data_toolkit — 132"]
        T15["test_eval — 50"]
    end

    T1 --> M1["scoring/dass21 — 100%"]
    T2 --> M2["scoring/pss10 — 100%"]
    T3 --> M3["scoring/__init__ — 100%"]
    T4 --> M4["llm/chain — 85%"]
    T4 --> M5["llm/safety — 100%"]
    T12 --> M5
    T5 --> M6["nlp/emotion + lexicon"]
    T6 --> M7["rag/ingest + store"]
    T7 --> M8["rag/retriever — 100%"]
    T8 --> M9["api/main — 97%"]
    T8 --> M10["api/services — 90%"]
    T9 --> M11["db/models — 100%"]
    T10 --> M12["eval/baselines"]
    T11 --> M13["eval/ablation"]
    T13 --> M14["eval/human-eval"]
    T14 --> M15["eval/synthetic"]
    T15 --> M16["eval/evaluate"]

    classDef full fill:#e6f4ea,stroke:#2d7a4d
    class M1,M2,M3,M5,M8,M11 full
```

Green nodes are at 100 % statement coverage: both scoring engines, the ground-truth derivation, the crisis rule, the retriever, and the persistence models — i.e. everything on the deterministic correctness path.

---

## 7. Entry points

| Command | Entry point | Purpose |
|---|---|---|
| `uvicorn app.api.main:app` | [app/api/main.py](../app/api/main.py) | Backend, port 8000 |
| `streamlit run streamlit_app/Home.py` | [streamlit_app/Home.py](../streamlit_app/Home.py) | Frontend, port 8501 |
| `python -m app.rag.ingest` | [app/rag/ingest.py](../app/rag/ingest.py) | Build the 23-chunk vector store |
| `python -m app.eval.compare` | [app/eval/compare.py](../app/eval/compare.py) | Baseline comparison table |
| `python -m app.eval.ablation` | [app/eval/ablation.py](../app/eval/ablation.py) | 5-configuration ablation |
| `python -m app.eval.crisis_eval` | [app/eval/crisis_eval.py](../app/eval/crisis_eval.py) | Crisis-rule evaluation |
| `python research/generate_dataset.py` | [research/generate_dataset.py](../research/generate_dataset.py) | Regenerate the dataset |
| `python research/phobert_finetune.py` | [research/phobert_finetune.py](../research/phobert_finetune.py) | Fine-tune the classifier |
| `python scripts/export_dataset.py` | [scripts/export_dataset.py](../scripts/export_dataset.py) | Anonymised research export |
| `python report/build_docx.py` | [report/build_docx.py](../report/build_docx.py) | Rebuild the thesis `.docx` |
| `pytest tests/ -q` | — | 198 tests |

---

## 8. Related documents

| Document | Contents |
|---|---|
| [docs/AUDIT.md](AUDIT.md) | Full codebase audit with file:line references |
| [docs/FEATURE_MATRIX.md](FEATURE_MATRIX.md) | Feature status, effort, grade impact |
| [docs/RISKS.md](RISKS.md) | Top committee questions and current answers |
| [docs/RESULTS.md](RESULTS.md) | Generated result tables |
| [report/PreThesis_Report.md](../report/PreThesis_Report.md) | The thesis report |
| [report/CITATIONS_TO_VERIFY.md](../report/CITATIONS_TO_VERIFY.md) | References requiring confirmation |
