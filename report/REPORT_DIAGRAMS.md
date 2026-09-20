# Diagrams for the HCMIU LaTeX report

> **Đã render sẵn.** Tất cả 12 diagram đã có PNG trong `images/`. Sau khi sửa một khối,
> chạy lại `python report/render_diagrams.py` (hoặc `python report/render_diagrams.py er`
> để chỉ render file có tên chứa `er`), rồi build lại report bằng `.\build.ps1`.
> Cách thủ công qua mermaid.live bên dưới vẫn dùng được.

Mỗi khối dưới đây là một hình trong report LaTeX. Cách dùng thủ công:

1. Dán khối vào <https://mermaid.live> → *Actions* → **PNG** (scale 2×, nền trắng).
2. Lưu đúng **tên file** ghi ở tiêu đề mỗi khối vào thư mục
   `report/International_University__HCMIU___VNU__Pre_thesis_and_Thesis_LaTeX_Template__1_/images/`.
3. Compile lại. Report dùng macro `\diagram{...}`: khi file PNG **chưa có**, LaTeX
   in một khung "Insert diagram …" thay cho hình (không lỗi compile); khi file có,
   hình tự thay vào đúng chỗ.

Nếu hình quá rộng cho trang A4, đổi `flowchart LR` ↔ `flowchart TD`.

| # | File | Label trong .tex | Chương / mục |
|---|---|---|---|
| 1 | `diagram_use_case.png` | `fig:usecase` | Ch. 3 Methodology → Use Case Diagram |
| 2 | `diagram_system_overview.png` | `fig:overview` | Ch. 3 Methodology → System Overview |
| 3 | `diagram_architecture.png` | `fig:architecture` | Ch. 4 Prototyping → System Architecture |
| 4 | `diagram_sequence.png` | `fig:sequence` | Ch. 4 Prototyping → System Architecture |
| 5 | `diagram_crisis_procedure.png` | `fig:crisisproc` | Ch. 4 Prototyping → Strategy 2 |
| 6 | `diagram_label_fusion.png` | `fig:fusion` | Ch. 4 Prototyping → Strategy 3 |
| 7 | `diagram_data_pipeline.png` | `fig:datapipeline` | Ch. 5 Implementation → Dataset Generation |
| 8 | `diagram_rag_pipeline.png` | `fig:ragpipeline` | Ch. 5 Implementation → Retrieval-Augmented Advisory Module |
| 9 | `diagram_er.png` | `fig:er` | Ch. 5 Implementation → Persistence |
| 10 | `diagram_ui_flow.png` | `fig:uiflow` | Ch. 5 Implementation → Frontend |
| 11 | `diagram_deployment.png` | `fig:deployment` | Ch. 5 Implementation → Deployment and CI |
| 12 | `diagram_eval_provenance.png` | `fig:provenance` | Ch. 6 Results → Experiment Setup |

**Ảnh chụp màn hình (không phải Mermaid)** — chụp từ app đang chạy và lưu cùng thư mục
`images/`; khi chưa có file, LaTeX in khung "Insert screenshot …":

| File | Label | Nội dung nên chụp |
|---|---|---|
| `screenshot_consent.png` | `fig:ss-consent` | Trang Home với checklist đồng ý |
| `screenshot_dass21.png` | `fig:ss-dass` | Trang DASS-21 đang làm dở (thấy bộ đếm tiến độ) |
| `screenshot_results.png` | `fig:ss-results` | Trang Results: level badge, gauge, giải thích, 3 gợi ý, nguồn |
| `screenshot_crisis.png` | `fig:ss-crisis` | Trạng thái crisis (nhập câu kiểu "I want to end my life" để kích hoạt) |
| `screenshot_history.png` | `fig:ss-history` | Trang History với biểu đồ xu hướng và nút xoá dữ liệu |

**Biểu đồ số liệu** (`fig_*.png`) đã được sinh sẵn bằng `python report/make_report_figures.py`.

---

## 1 — `diagram_use_case.png`

Mermaid không có use-case diagram gốc; khối này mô phỏng bằng flowchart (actor ở
hai bên, use case hình bầu dục trong khung hệ thống). Nếu thầy/cô yêu cầu đúng ký
hiệu UML, vẽ lại bằng draw.io theo đúng các use case này.

```mermaid
flowchart LR
    ST(["👤 Student"])
    RS(["👤 Researcher"])
    LLM(["🖥 LLM provider<br/>(external system)"])

    subgraph SYS["Screening system"]
        direction TB
        UC1(["Give informed consent"])
        UC2(["Write free-text reflection"])
        UC3(["Complete DASS-21"])
        UC4(["Complete PSS-10"])
        UC5(["Provide academic & lifestyle context"])
        UC6(["View stress assessment & suggestions"])
        UC7(["Receive crisis helplines"])
        UC8(["View assessment history"])
        UC9(["Delete own data"])
        UC10(["Export anonymised dataset"])
        UC11(["Run evaluation harness"])
    end

    ST --- UC1
    ST --- UC2
    ST --- UC3
    ST --- UC4
    ST --- UC5
    ST --- UC6
    ST --- UC8
    ST --- UC9
    UC6 -. "«include» consent checked" .-> UC1
    UC7 -. "«extend» when crisis rule fires" .-> UC6
    UC6 --- LLM
    RS --- UC10
    RS --- UC11

    classDef actor fill:#F1F5F9,stroke:#1E293B,stroke-width:2px,color:#1E293B
    classDef uc fill:#E8F0FE,stroke:#2F63BD,stroke-width:1.5px,color:#1E293B
    classDef crisis fill:#FEE2E2,stroke:#B3261E,stroke-width:1.5px,color:#1E293B
    class ST,RS,LLM actor
    class UC1,UC2,UC3,UC4,UC5,UC6,UC8,UC9,UC10,UC11 uc
    class UC7 crisis
```

---

## 2 — `diagram_system_overview.png`

Tổng quan cấp cao: input → xử lý → output.

```mermaid
flowchart LR
    subgraph IN["Inputs"]
        T["Free text<br/>(Vietnamese or English)"]
        D["DASS-21<br/>21 items, 0–3"]
        P["PSS-10<br/>10 items, 0–4"]
        C["Context<br/>study · sleep · finance · support"]
    end

    subgraph CORE["Processing"]
        A["Text analysis<br/>PhoBERT + stress lexicon"]
        S["Psychometric scoring<br/>deterministic"]
        G{{"Crisis gate"}}
        R["Knowledge retrieval<br/>23 curated chunks"]
        L["LLM explanation<br/>grounded + cited"]
    end

    subgraph OUT["Outputs"]
        O1["Stress level<br/>Low · Moderate · High · Severe"]
        O2["Explanation +<br/>3 coping suggestions"]
        O3["Helplines<br/>(crisis path only)"]
    end

    T --> A
    D --> S
    P --> S
    A --> G
    S --> G
    G -- "clear" --> R --> L
    C --> L
    S --> O1
    L --> O2
    G -- "fires" --> O3

    classDef gate fill:#F1F5F9,stroke:#1E293B,stroke-width:3px,color:#1E293B
    classDef stop fill:#FEE2E2,stroke:#B3261E,stroke-width:2px,color:#1E293B
    class G gate
    class O3 stop
```

---

## 3 — `diagram_architecture.png`

```mermaid
flowchart TB
    subgraph UI["Streamlit UI (7 pages)"]
        direction LR
        P0["Home / consent"] --> P1["Share feelings"] --> P2["DASS-21"] --> P3["PSS-10"] --> P4["Context"] --> P5["Results"] --> P6["History"]
    end

    subgraph API["FastAPI endpoints"]
        E1["GET /health"]
        E2["POST /assess/text"]
        E3["POST /assess/questionnaire"]
        E4["POST /assess/full"]
        E5["GET /history/{student_id}"]
        E6["DELETE /session/{student_id}"]
    end

    subgraph SVC["Service layer"]
        S1["NLP analysis<br/>app/nlp"]
        S2["DASS-21 / PSS-10 scoring<br/>app/scoring"]
        S3["Crisis rule<br/>app/llm/safety + crisis_patterns"]
        S4["Retriever<br/>app/rag"]
        S5["LLM chain (LCEL)<br/>app/llm/chain"]
    end

    subgraph DATA["Data layer"]
        D1[("SQLite<br/>5 tables")]
        D2[("ChromaDB<br/>23 chunks, cosine HNSW")]
        D3[["PhoBERT checkpoint<br/>models/phobert-stress"]]
        D4[["MiniLM-L12 multilingual<br/>embedder"]]
    end

    EXT(["openai/gpt-oss-120b<br/>via OpenAI-compatible API (Groq)"])

    P5 -- "HTTP / JSON" --> E4
    P6 --> E5
    P6 --> E6
    E2 & E3 & E4 --> SVC
    S1 --> D3
    S4 --> D2
    D2 --- D4
    SVC --> D1
    E5 & E6 --> D1
    S5 --> EXT

    classDef ext fill:#FFF7ED,stroke:#92400E,stroke-width:2px,color:#1E293B
    class EXT ext
```

---

## 4 — `diagram_sequence.png`

Thứ tự đúng như code (`run_full_assessment`): phân tích + chấm điểm → crisis gate →
lưu DB → retrieval → LLM.

```mermaid
sequenceDiagram
    autonumber
    actor S as Student
    participant UI as Streamlit
    participant API as FastAPI
    participant NL as NLP (PhoBERT + lexicon)
    participant SC as Scoring
    participant CR as Crisis rule
    participant DB as SQLite
    participant RG as Retriever
    participant LM as LLM

    S->>UI: consent, text, DASS-21, PSS-10, context
    UI->>API: POST /assess/full
    API->>NL: analyze(text)
    API->>SC: score_dass21 / score_pss10
    API->>CR: check_crisis(text, answers, depression severity)
    alt crisis detected
        CR-->>API: is_crisis = true
        API-->>UI: helpline message only
        Note over API,DB: nothing persisted, retrieval and LLM never called
    else cleared
        API->>DB: save text, questionnaire, context
        API->>RG: retrieve(sentence + keywords, k = 4)
        alt no passages
            RG-->>API: []
            API-->>UI: deterministic scores + "advice withheld" reason
        else passages found
            API->>LM: prompt(evidence + passages with chunk ids)
            LM-->>API: JSON (level, reasoning, suggestions, citations)
            API->>API: drop citations not in retrieved set
            API->>DB: save prediction
            API-->>UI: questionnaire level (headline) + explanation + suggestions + sources
        end
    end
```

---

## 5 — `diagram_label_fusion.png`

```mermaid
flowchart TD
    Q["DASS-21 stress severity"] --> MAX
    P["PSS-10 category"] --> MAX
    MAX["Map both to the unified scale<br/>take the MORE SEVERE"] --> GT["Instrument label<br/><b>headline</b>"]

    T["Student's free text"] --> M["LLM reads all evidence"]
    Q -.-> M
    P -.-> M
    M --> MP["Model's predicted level"]

    GT --> UI["Results page"]
    MP --> UI
    UI --> D{"Questionnaire<br/>completed?"}
    D -- "no" --> MH["Model level is shown<br/>as the headline"]
    D -- "yes" --> DIF{"Labels differ?"}
    DIF -- "yes" --> SAY["Show questionnaire level<br/>and state the divergence"]
    DIF -- "no" --> SHOW["Show level + explanation"]

    classDef inst fill:#E8F0FE,stroke:#2F63BD,stroke-width:2px,color:#1E293B
    classDef model fill:#FFF7ED,stroke:#92400E,stroke-width:2px,color:#1E293B
    classDef out fill:#E7F6E9,stroke:#2E7D32,stroke-width:2px,color:#1E293B
    class Q,P,MAX,GT inst
    class T,M,MP model
    class SAY,SHOW,MH,UI out
```

---

## 6 — `diagram_crisis_procedure.png`

```mermaid
flowchart TD
    OLD["Old rule: flat phrase list<br/>held-out recall 0.200"] --> TRAP{"Add the published<br/>false negatives to the list?"}
    TRAP -- "tuning on the test set" --> NO["Rejected"]
    TRAP -- "instead" --> S1["Step 1 · Write a new 60-item bilingual set<br/>freeze it, record SHA-256"]
    S1 --> S2["Step 2 · Rebuild the rule from 6 constructs<br/>explicit · passive wish · existence ·<br/>burden · preparation · escape"]
    S2 --> S3["Step 3 · Measure held-out once,<br/>report the first number"]
    S3 --> S4["Step 4 · Demote VI and EN sets to development;<br/>fix regressions and idiom false positives"]
    S4 --> S5["Step 5 · Re-measure held-out:<br/>identical numbers"]
    S5 --> RES["Held-out: P 1.000 · R 0.867 · F1 0.929<br/>indirect ideation 0/14 → 11/14"]
    RES --> LIM["Remaining limitation:<br/>same author wrote patterns and held-out set"]

    classDef bad fill:#FEE2E2,stroke:#B3261E,stroke-width:2px,color:#1E293B
    classDef step fill:#E8F0FE,stroke:#2F63BD,stroke-width:2px,color:#1E293B
    classDef good fill:#E7F6E9,stroke:#2E7D32,stroke-width:2px,color:#1E293B
    classDef warn fill:#FFF7ED,stroke:#92400E,stroke-width:2px,color:#1E293B
    class OLD,NO bad
    class S1,S2,S3,S4,S5 step
    class RES good
    class LIM warn
```

---

## 7 — `diagram_data_pipeline.png`

```mermaid
flowchart TD
    A["generate_dataset.py<br/>seed 42 · 500 records<br/>latent stress θ ~ Beta mixture"] --> B["Exact deduplication<br/>466 unique texts"]
    B --> C["Stratified split<br/>seed 42, frozen to disk"]
    C --> D["train 326 · val 70 · test 70"]
    D --> E["phobert_finetune.py<br/>train on train, select on val"]
    D --> F["derive_ground_truth()<br/>unified 4-class label"]
    F --> G["Evaluation harness<br/>identical split for every system"]
    E --> G
    D --> H["check_leakage.py<br/>near-duplicate audit"]
```

---

## 8 — `diagram_rag_pipeline.png`

```mermaid
flowchart TB
    subgraph ING["Offline ingestion"]
        direction TB
        K["6 Markdown documents<br/>data/knowledge/"] --> SPL["Split at ## headings<br/>prepend document title<br/>split sections > 1,500 chars"]
        SPL --> ID["Deterministic ids<br/>file.md::index"]
        ID --> EMB["Embed with<br/>paraphrase-multilingual-MiniLM-L12-v2"]
        EMB --> VS[("ChromaDB<br/>23 chunks, cosine HNSW")]
    end

    subgraph QRY["Online retrieval"]
        direction TB
        TXT["Student sentence (≤ 300 chars)"] --> QB["build_rag_query()<br/>sentence + matched keywords"]
        KW["Lexicon keywords"] --> QB
        QB --> TOPK["Top k = 4<br/>no threshold, no rerank"]
        VS --> TOPK
        TOPK --> EMPTY{"any passages?"}
        EMPTY -- "no" --> REF["Refuse to generate<br/>state reason"]
        EMPTY -- "yes" --> PR["Prompt with chunk ids"]
        PR --> LLM["LLM → citations"]
        LLM --> VER["Keep only citations<br/>present in retrieved set"]
    end
```

---

## 9 — `diagram_er.png`

```mermaid
erDiagram
    USERS ||--o{ TEXT_ENTRIES : writes
    USERS ||--o{ QUESTIONNAIRE_RESPONSES : completes
    USERS ||--o{ STRESS_CONTEXT : provides
    USERS ||--o{ PREDICTIONS : receives

    USERS {
        string student_id PK "UUID"
        int age
        string gender
        int year_of_study
        string major
        string university
        datetime created_at
    }
    TEXT_ENTRIES {
        string entry_id PK
        string student_id FK
        text raw_text
        int text_length
        string language "vi / en / mixed"
        string emotion_label
        json emotion_scores
        string sentiment_polarity
        json stress_keywords
        datetime timestamp
    }
    QUESTIONNAIRE_RESPONSES {
        string response_id PK
        string student_id FK
        int dass_q1_to_q21 "21 columns"
        int depression_score
        int anxiety_score
        int stress_score
        string stress_level_dass
        int pss_q1_to_q10 "10 columns"
        int pss_total_score
        string pss_stress_category
        datetime created_at
    }
    STRESS_CONTEXT {
        string context_id PK
        string student_id FK
        float study_hours_per_week
        bool is_exam_period
        int assignment_workload
        float gpa
        float sleep_hours_avg
        int financial_stress
        int social_support_level
        json coping_strategies
        bool has_sought_help
        datetime created_at
    }
    PREDICTIONS {
        string prediction_id PK
        string student_id FK
        string ground_truth_label
        string llm_predicted_label
        float llm_confidence
        json rag_retrieved_context
        text llm_explanation
        datetime created_at
    }
```

---

## 10 — `diagram_ui_flow.png`

```mermaid
flowchart TD
    H["Home<br/>6-point consent checklist<br/>optional background"] --> GATE{"Consent<br/>given?"}
    GATE -- "no" --> H
    GATE -- "yes" --> F["1 · Share feelings<br/>optional mood prompts"]
    F --> D["2 · DASS-21<br/>live completion counter"]
    D --> P["3 · PSS-10"]
    P --> C["4 · Context<br/>academic · lifestyle · coping"]
    C --> R["5 · Results"]
    R --> CR{"crisis?"}
    CR -- "yes" --> HL["Helpline block only"]
    CR -- "no" --> RES["Meaning first → level badge ·<br/>gauge · subscales · radar ·<br/>explanation · 3 suggestions · sources"]
    RES --> HI["6 · History<br/>trend · timeline · delete my data"]

    classDef stop fill:#FEE2E2,stroke:#B3261E,stroke-width:2px,color:#1E293B
    class HL stop
```

---

## 11 — `diagram_deployment.png`

```mermaid
flowchart LR
    subgraph HOST["Docker Compose host"]
        subgraph C1["container: api"]
            UV["Uvicorn + FastAPI<br/>:8000"]
            M1[["PhoBERT + MiniLM<br/>lazy-loaded"]]
        end
        subgraph C2["container: ui"]
            STL["Streamlit<br/>:8501"]
        end
        V1[("volume: data/<br/>SQLite · ChromaDB · knowledge")]
        V2[("volume: models/")]
    end
    BR(["Student browser"]) -- "HTTPS" --> STL
    STL -- "HTTP JSON" --> UV
    UV --- V1
    UV --- V2
    UV -- "OpenAI-compatible API" --> GQ(["Groq<br/>openai/gpt-oss-120b"])
    GIT(["GitHub repository"]) -. "push / pull request" .-> GH(["GitHub Actions CI<br/>ruff + pytest, Ubuntu, Py 3.11, CPU torch"])
    GIT -. "docker compose build" .-> HOST
```

---

## 12 — `diagram_eval_provenance.png`

```mermaid
flowchart LR
    subgraph SRC["Committed source data"]
        D1["stress_dataset.csv<br/>466 distinct texts"]
        D2["crisis_testset*.jsonl<br/>3 labelled sets"]
        D3["retrieval_queries.jsonl<br/>57 labelled queries"]
        D4["knowledge/*.md<br/>23 chunks"]
    end
    subgraph RUN["Evaluation scripts"]
        R1["app.eval.compare"]
        R2["app.eval.ablation"]
        R3["app.eval.crisis_eval"]
        R4["app.eval.retrieval_eval"]
        R5["app.eval.latency_eval"]
        R6["scripts/check_leakage.py"]
    end
    subgraph ART["data/eval artefacts"]
        A1["comparison.csv / .md"]
        A2["ablation.csv / .md"]
        A3["crisis_eval*.md"]
        A4["retrieval_eval.md"]
        A5["latency.json / .md"]
        A6["leakage.md"]
    end
    CACHE[("LLM response cache<br/>SHA-256 of full input")]
    D1 --> R1 --> A1
    D1 --> R2 --> A2
    D2 --> R3 --> A3
    D3 --> R4 --> A4
    D4 --> R4
    D1 --> R5 --> A5
    D1 --> R6 --> A6
    R1 <--> CACHE
    R2 <--> CACHE
    ART --> FIG["report/make_report_figures.py<br/>→ images/fig_*.png"] --> REP["LaTeX report"]
```
