# Runbook — running the system

Every command runs from the project root. The PowerShell forms below are what
this project is developed against (Windows); the underlying commands are the
same everywhere.

Each step here has been executed and verified, most recently on 2026-09-23.

---

## 0. First run on a new machine

```powershell
python --version    # 3.11+ required
python -c "import fastapi, streamlit, torch, chromadb; print('deps OK')"
```

If anything is missing:

```powershell
pip install -r requirements.txt
```

Check the knowledge base is loaded into Chroma. **It must report 23:**

```powershell
python -c "import sys; sys.path.insert(0,'.'); from app.rag.store import get_collection; print('chunks:', get_collection().count())"
```

If it reports `0`, ingest:

```powershell
python -m app.rag.ingest
```

`data/chroma/` is not in git — it is rebuilt from `data/knowledge/*.md` by that
command. Note that ingest upserts with ids derived from the filename, so if you
rename a knowledge file you must delete `data/chroma/` first or the old chunks
linger.

---

## 1. Free the ports

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8501 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## 2. Start the two processes, in two separate windows

**Window 1 — the API:**

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete.`

**Window 2 — the interface:**

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m streamlit run streamlit_app/Home.py --server.port 8501
```

`PYTHONIOENCODING=utf-8` is not optional on a Windows console: without it the
Vietnamese text in logs and knowledge passages raises a codec error.

---

## 3. Warm the models — do not skip this

The first request loads PhoBERT (~8 s) and the sentence embedder (~11 s), so a
cold system shows roughly **25 seconds of blank screen**. Spend that here, not
in front of an audience.

**Window 3:**

```powershell
python scripts/warm.py
```

Expected output — the first `health` line taking ~25 s is normal:

```
  [ok]   health              0.0s   {'status': 'ok', ..., 'knowledge_chunks': 23}
  [ok]   PhoBERT + scoring   2.7s   headline label: High
  [ok]   retrieval                   4 passages
  [ok]   generation                  advice present, citations verified

  second health call: 0.03s  (warm)
Ready.
```

The script diagnoses rather than leaving you to guess. It reports a clear cause
when the API is unreachable, when `knowledge_chunks` is 0, when generation is
unavailable because the LLM quota is exhausted, and when the second health call
is still slow (meaning nothing actually warmed).

One deliberate detail: the warm-up submits DASS-21 items 17 and 21 as `0`. Those
are the two risk items, and a non-zero answer would route the request into the
crisis branch — which returns helpline text without calling retrieval or the
generator, leaving exactly the two slow components cold.

---

## 4. Pre-flight checks

```powershell
curl.exe -s http://127.0.0.1:8000/health
curl.exe -s http://127.0.0.1:8501/_stcore/health
```

Expect `{"status":"ok",...,"knowledge_chunks":23}` and `ok`. The second health
call must come back in under a second; ~25 s means the system is still cold.

```powershell
Start-Process "http://localhost:8501"
```

Two browser settings that are easy to forget:

1. **Turn off auto-translate** in Edge/Chrome, or the interface renders as a
   mix of English and Vietnamese.
2. To demo from the consent screen, open a **private window** — a consent that
   has already been accepted is remembered.

---

## 5. Inputs that produce each outcome

| Target outcome | DASS-21 | PSS-10 |
|---|---|---|
| **High** (main demo) | all **2**, except items **17 & 21 = 0** | any |
| Severe | all **3**, except items **17 & 21 = 0** | any |
| Moderate | all **0** | all **0** |
| Low | all **0** | items **4, 5, 7, 8 = 4**, rest **0** |
| **Crisis** (intentional) | all **0**, except items **17 & 21 = 3** | any |

Items 17 and 21 are the risk items — *"I felt I wasn't worth much as a person"*
and *"I felt that life was meaningless"*. Answering **2** or higher on both
triggers the crisis screen. That is correct behaviour, not a fault.

To demo the crisis path from free text instead, which is stronger because it
needs no questionnaire:

```
I just want to sleep for a very long time and never wake up again.
```

This is published false negative #16: the original phrase-list rule missed it
and the rebuilt construct-based rule catches it.

Note that **Save** on the "Share how you feel" page does not call the API. The
analysis runs when you press **Analyse now** on the Results page.

---

## 6. When the LLM quota is exhausted

```powershell
python scripts/check_llm.py     # section 6 reports the real daily allowance
```

The application still runs every deterministic component and **states the
reason** rather than showing an empty panel. `data/eval/llm_cache/` holds real
outputs from the same chain if you need to show generated advice without
spending quota.

Groq's daily token cap is the limit that stops long evaluation runs, and it
appears in **no response header** — only in the body of a 429. Never infer
headroom from a successful small request.

---

## 7. Stop

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8501 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Blank page for ~25 s | Not warmed | Run §3 |
| `knowledge_chunks: 0` | Chroma is empty | `python -m app.rag.ingest` |
| Interface half in Vietnamese | Browser auto-translate | Turn it off |
| No advice, with a stated reason | Groq quota exhausted | §6 |
| Jumps to the crisis screen | DASS items 17/21 ≥ 2 | Set them to 0 or 1 |
| `ModuleNotFoundError: app` | Wrong working directory | `cd` to the project root |
| `UnicodeEncodeError` in the console | Missing encoding | `$env:PYTHONIOENCODING = "utf-8"` |
