# Diagrams for the defence deck

Paste each block into <https://mermaid.live>, export PNG at 2x, and paste it into
the dashed frame on the matching slide of `PreThesis_Slides_v4.pptx`. Colours
match `streamlit_app/ui/tokens.py`, so the diagrams, the deck and the running
application look like one piece of work.

| Block | Export as | Slide in v4 | Role |
|---|---|---|---|
| 1 — System architecture | `fig_1.png` | **5** | main talk — the one to show if you show only one |
| 3 — Safety-rule procedure | `fig_3.png` | **10** | main talk |
| 2 — Where the headline label comes from | `fig_2.png` | 18 | backup, Q&A only |
| 4 — Evidence provenance | `fig_4.png` | 19 | backup, Q&A only |

---

## 1 — System architecture  → slide 5  (`fig_1.png`)

The single most important diagram in the deck. The gate in the middle is the
whole argument: **everything to its left is a pure function and cannot store,
send or show anything; nothing to its right runs until the gate has cleared.**

The execution order is drawn as the code actually runs (`services.py`,
`run_full_assessment`): the classifier and the scoring execute *first*, then the
crisis gate, and only then persistence, retrieval and generation. The gate
cannot run earlier — it consumes the DASS-21 depression severity that the
scoring step produces. An earlier version of this diagram numbered the crisis
rule as step 1; that was wrong, and a panel member reading the code would have
seen it.

```mermaid
flowchart LR
    IN["Student input<br/><i>free text · DASS-21 · PSS-10 · context</i>"]

    subgraph PURE["1 · PURE COMPUTATION — offline, no side effects"]
        direction TB
        NLP["PhoBERT classifier<br/><b>59 ms</b><br/><i>Vietnamese input only;<br/>lexicon otherwise</i>"]
        SCORE["Psychometric scoring<br/><b>0.03 ms</b><br/>DASS-21 + PSS-10"]
    end

    CRISIS{{"2 · CRISIS GATE<br/><b>0.05 ms</b><br/>6 clinical constructs<br/>+ DASS risk items 17 / 21"}}

    subgraph SIDE["3 – 5 · CONSEQUENTIAL — runs only after the gate clears"]
        direction TB
        DB[("3 · Persist<br/>text · answers · context")]
        RAG["4 · Retrieval k=4<br/><b>28 ms</b><br/>23 curated chunks"]
        LLM["5 · Generation<br/>grounded + cited<br/><i>external · may fail · never authoritative</i>"]
    end

    HELP["Helplines only<br/><i>LLM never called<br/>nothing stored</i>"]
    OUT["Results page<br/><b>headline from the questionnaire</b><br/>model explains, does not decide"]
    DEG["Deterministic results<br/>+ stated reason"]

    IN --> NLP
    IN --> SCORE
    NLP --> CRISIS
    SCORE --> CRISIS
    CRISIS -- "fires" --> HELP
    CRISIS -- "clear" --> DB --> RAG
    NLP -. "keywords shape the query" .-> RAG
    RAG -- "nothing found" --> DEG
    RAG -- "passages found" --> LLM
    LLM -- "unavailable" --> DEG
    LLM -- "ok" --> OUT

    classDef pure fill:#E8F0FE,stroke:#2F63BD,stroke-width:2px,color:#1E293B
    classDef gate fill:#F1F5F9,stroke:#1E293B,stroke-width:3px,color:#1E293B
    classDef gen fill:#FFF7ED,stroke:#92400E,stroke-width:2px,color:#1E293B
    classDef stop fill:#FEE2E2,stroke:#B3261E,stroke-width:2px,color:#1E293B
    classDef ok fill:#E7F6E9,stroke:#2E7D32,stroke-width:2px,color:#1E293B
    class NLP,SCORE,DB,RAG pure
    class CRISIS gate
    class LLM gen
    class HELP stop
    class OUT,DEG ok
```

**Say over it:** *"Everything left of the gate is a pure function — it cannot
store, send or show anything. Nothing is written to the database and no
external service is called until the gate has cleared. That is the safety
property, stated precisely — and the gate costs 0.05 milliseconds."*

**If asked why the classifier runs before the gate:** *"Because it has no side
effects. The gate reads the student's text and the DASS scores; the
classifier's output only matters later, for shaping the retrieval query and the
prompt. Running a pure function before the gate cannot leak or store anything."*

---

## 2 — Where the headline label comes from  → slide 18, backup for Q&A  (`fig_2.png`)

The answer to *"the model could contradict the questionnaire — which one does
the student see?"*. Worth having ready even if you do not show it.

```mermaid
flowchart TD
    Q["DASS-21 stress severity"] --> MAX
    P["PSS-10 category"] --> MAX
    MAX["Take the MORE SEVERE of the two<br/><i>conservative by design</i>"] --> GT["Ground-truth label<br/><b>this is the headline</b>"]

    T["Student's free text"] --> M["Language model<br/>reads all evidence"]
    Q -.-> M
    P -.-> M
    M --> MP["Model's own reading"]

    GT --> UI["Results page"]
    MP --> UI
    UI --> D{"Do they<br/>differ?"}
    D -- "yes" --> SAY["Say so explicitly:<br/><i>'the model read your writing as X,<br/>which differs from your questionnaire result of Y'</i>"]
    D -- "no" --> QUIET["Show the level<br/>and the explanation"]

    classDef inst fill:#E8F0FE,stroke:#2F63BD,stroke-width:2px,color:#1E293B
    classDef model fill:#FFF7ED,stroke:#92400E,stroke-width:2px,color:#1E293B
    classDef out fill:#E7F6E9,stroke:#2E7D32,stroke-width:2px,color:#1E293B
    class Q,P,MAX,GT inst
    class T,M,MP model
    class SAY,QUIET,UI out
```

**Say over it:** *"The validated instrument owns the headline. The model
explains and suggests. Where they disagree the student is told, rather than the
disagreement being hidden."*

---

## 3 — How the safety rule was rebuilt without cheating  → slide 10  (`fig_3.png`)

This is the methodological story, and it is the one that separates the project
from a coursework submission. The diagram makes the *order* visible, which is
the whole point.

```mermaid
flowchart TD
    OLD["Old rule: flat phrase list<br/>held-out recall <b>0.200</b>"] --> PROB

    PROB["Problem: the 12 failures<br/>were already published"] --> TRAP
    TRAP{"Add them to<br/>the phrase list?"}
    TRAP -- "that is tuning<br/>against the test set" --> NO["Rejected"]

    TRAP -- "instead" --> S1
    S1["<b>1.</b> Write a NEW 60-item bilingual set<br/>FREEZE it · SHA-256 recorded"]
    S2["<b>2.</b> Rebuild the rule from 6 clinical constructs<br/><i>explicit · passive wish · existence ·<br/>burden · preparation · escape</i>"]
    S3["<b>3.</b> Measure ONCE<br/>report the first number"]
    S4["<b>4.</b> Demote the 2 older sets<br/>to development sets"]
    S5["<b>5.</b> Re-measure held-out<br/><b>identical numbers</b>"]

    S1 --> S2 --> S3 --> RESULT
    S3 --> S4 --> S5 --> RESULT
    RESULT["Held-out result<br/><b>P 1.000 · R 0.867 · F1 0.929</b><br/>indirect ideation 0/14 → 11/14"]

    RESULT --> CAVEAT["Remaining limitation:<br/><i>one author wrote both the patterns<br/>and the held-out set</i>"]

    classDef bad fill:#FEE2E2,stroke:#B3261E,stroke-width:2px,color:#1E293B
    classDef step fill:#E8F0FE,stroke:#2F63BD,stroke-width:2px,color:#1E293B
    classDef good fill:#E7F6E9,stroke:#2E7D32,stroke-width:2px,color:#1E293B
    classDef warn fill:#FFF7ED,stroke:#92400E,stroke-width:2px,color:#1E293B
    class OLD,PROB,NO bad
    class S1,S2,S3,S4,S5 step
    class RESULT good
    class CAVEAT warn
```

**Say over it:** *"Fixing it honestly was harder than fixing it. The order came
first, and the order is what makes the number mean anything."*

---

## 4 — Evidence provenance  → slide 19, backup for Q&A  (`fig_4.png`)

Every number on a slide traces to a script. Use this if the panel questions
whether the figures are reproducible.

```mermaid
flowchart LR
    subgraph SRC["Committed source data"]
        D1["stress_dataset.csv<br/>500 rows · 466 distinct texts · seed 42"]
        D2["crisis_testset*.jsonl<br/>3 labelled sets"]
        D3["retrieval_queries.jsonl<br/>57 labelled queries"]
        D4["knowledge/*.md<br/>23 chunks"]
    end

    subgraph RUN["Scripts — each writes its own artefact"]
        R1["app.eval.compare"]
        R2["app.eval.crisis_eval"]
        R3["app.eval.retrieval_eval"]
        R4["app.eval.latency_eval"]
        R5["scripts/check_leakage.py"]
        R6["app.eval.ablation"]
        R7["app.eval.make_figures"]
    end

    subgraph ART["data/eval/ artefacts"]
        A1["comparison.md"]
        A2["crisis_eval*.md"]
        A3["retrieval_eval.md"]
        A4["latency.md"]
        A5["leakage.md"]
        A6["ablation.md<br/><b>NOT RUN marker</b>"]
        A7["fig_4_*.png<br/>report figures"]
    end

    D1 --> R1 --> A1
    D2 --> R2 --> A2
    D3 --> R3 --> A3
    D4 --> R3
    D1 --> R4 --> A4
    D1 --> R5 --> A5
    D1 --> R6 --> A6
    A1 --> R7
    D1 --> R7
    R7 --> A7

    A1 --> DECK["Report · deck · script"]
    A2 --> DECK
    A3 --> DECK
    A4 --> DECK
    A5 --> DECK
    A6 --> DECK
    A7 --> DECK

    classDef src fill:#E8F0FE,stroke:#2F63BD,stroke-width:2px,color:#1E293B
    classDef run fill:#F1F5F9,stroke:#64748B,stroke-width:2px,color:#1E293B
    classDef art fill:#E7F6E9,stroke:#2E7D32,stroke-width:2px,color:#1E293B
    classDef gap fill:#FFF7ED,stroke:#92400E,stroke-width:2px,color:#1E293B
    class D1,D2,D3,D4 src
    class R1,R2,R3,R4,R5,R6,R7 run
    class A1,A2,A3,A4,A5,A7 art
    class A6 gap
    class DECK art
```

**Say over it:** *"No number in the report exists without a script that produced
it, and where a measurement has not been made the tooling writes an explicit
NOT RUN marker rather than letting a gap look like a zero."*

---

## Rendering notes

- **mermaid.live** → paste → *Actions* → *PNG*. Set **2×** scale for a projector.
- Save as `fig_1.png` … `fig_4.png` (numbers match the blocks above), then in
  PowerPoint paste each onto its slide and delete the dashed placeholder frame.
- If a diagram is too wide for 16:9, change `flowchart LR` to `flowchart TD`
  (or the reverse) — nothing else needs editing.
- Diagram 1 is the one to show if you only have time for one.
