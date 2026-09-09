# Running the LLM evaluations

Everything in this project except the language-model half is already measured.
This is the runbook for the half that is not, because it needs an API key.

**What one key unlocks**, all from the same frozen 70-item test split:

| Output | Command | Fills |
|---|---|---|
| `llm_zeroshot` + `llm_full` rows | `python -m app.eval.compare --dataset synthetic` | Table 4.3, objective O2 |
| 5-configuration ablation | `python -m app.eval.ablation --dataset synthetic` | Table 4.6, objective O3 |
| Model/instrument disagreement rate | `python -m app.eval.evaluate` | §5.4 |

Faithfulness (does the model actually use the passage it cites) also needs a
key, but the harness for it is not written yet; see §6.2 item 4 of the report.

Responses are cached on disk under `data/eval/llm_cache/` keyed by a hash of the
full input, model and endpoint. **A re-run costs nothing** and is deterministic,
so you pay for each distinct request once.

---

## Step 1 — Choose a provider

The client speaks the OpenAI API, but it does not have to talk to OpenAI. Set
`OPENAI_BASE_URL` and any OpenAI-compatible provider works.

| Provider | Free? | Base URL | Notes |
|---|---|---|---|
| **Ollama** (local) | Yes, fully | `http://localhost:11434/v1` | No key, **no quota**, no data leaves your machine. Needs a capable PC. **Best for this workload and for privacy.** |
| **Groq** | Free tier | `https://api.groq.com/openai/v1` | Fast, good JSON adherence. Free tier is token-capped; see quota planning below. |
| **Google Gemini** | Free tier | `https://generativelanguage.googleapis.com/v1beta/openai/` | Solid free quota. |
| **OpenRouter** | Some models free | `https://openrouter.ai/api/v1` | Append `:free` to a model id. Limits vary by model. |
| **OpenAI** | No | leave empty | What the report currently documents. |

So: **yes, free keys work.** They did not before — the code had no way to change
the endpoint. That was added on 2026-09-07 along with a tunable request
concurrency, because free tiers rate-limit.

> ### Two things you must not skip
>
> **1. Consent.** `docs/consent_form_vi.md` §4 tells participants their text goes
> to **OpenAI**. If you point the system at Groq or Google, that statement
> becomes false. Update the consent form, the in-app consent list in
> `streamlit_app/Home.py`, and the report before collecting any real data.
> For synthetic-data evaluation only, there is no participant, so no issue.
>
> **2. The report must name the model you actually used.** §4.4 and the abstract
> currently say `gpt-4o-mini`. A number produced by `gpt-oss-120b` on Groq is a
> different result and must be labelled as one.

---

## Step 2 — Get a key

**Groq:**

1. Sign in at `console.groq.com`.
2. Open **API Keys**, create one. It starts with `gsk_`.
3. Copy it immediately; it is shown once.

**Ollama**, if you prefer nothing leaving your machine:

```bash
# install from ollama.com, then:
ollama serve
ollama pull gpt-oss:20b     # or llama3.1:8b on a smaller machine
```

No key is needed, but the client still requires a non-empty string, so use the
literal `ollama`.

---

## Step 3 — Configure `.env`

Create `.env` in the project root if it does not exist. `.env.example` has
ready-made blocks to copy. For Groq:

```ini
OPENAI_API_KEY=gsk_your_real_key_here
OPENAI_MODEL=openai/gpt-oss-120b
OPENAI_BASE_URL=https://api.groq.com/openai/v1
LLM_CONCURRENCY=1
```

> **Do not use `llama-3.3-70b-versatile`.** Groq deprecated it for free and
> developer tiers on 2026-06-17 and names `openai/gpt-oss-120b` as the
> replacement. Being an OpenAI model, it is also better at the strict JSON this
> project requires.

`.env` is gitignored. Never commit a real key.

`LLM_CONCURRENCY` defaults to 4. Use **1** on the Groq free tier: the cap there
is 8,000 tokens per minute and one `llm_full` request is about 1,800 tokens, so
only four or five fit in a minute regardless of how many you send at once.

---

## Step 4 — Verify the connection before spending quota

One command checks configuration, connectivity, strict-JSON adherence and the
quota you are about to need:

```bash
python scripts/check_llm.py
```

It exits non-zero and says what is wrong if any step fails. The equivalent
one-liner, if you prefer:

```bash
python -c "
from langchain_openai import ChatOpenAI
from app.config import get_settings
s = get_settings()
llm = ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key,
                 base_url=s.openai_base_url or None, timeout=30)
print(llm.invoke('Reply with exactly: OK').content)
"
```

Expected: `OK`. If this fails, fix it here rather than inside a 70-item run.

| Error | Cause |
|---|---|
| `AuthenticationError` / 401 | Wrong key, or key does not match the base URL |
| `NotFoundError` / 404 | Model id not offered by this provider, or base URL missing `/v1` |
| `Connection refused` | Ollama not running (`ollama serve`) |
| 429 | Rate limited; lower `LLM_CONCURRENCY` |

Then check the app path end to end:

```bash
uvicorn app.api.main:app --port 8000
# in another terminal:
curl -s -X POST http://127.0.0.1:8000/assess/full \
  -H "Content-Type: application/json" \
  -d '{"raw_text":"I am overwhelmed by deadlines and cannot sleep at night."}'
```

`assessment` should now be an object rather than `null`.

---

## Quota planning (measured, not estimated)

Prompt sizes were measured against the real chain and the real corpus:

| Run | Requests | Input tokens |
|---|---:|---:|
| `llm_zeroshot` | 70 | ~9,500 |
| `llm_full` | 70 | ~126,000 |
| `ablation`, the 4 remaining configs | 280 | ~400,000 |
| **Total** | **420** | **~536,000** |

A single `llm_full` prompt is ~1,800 tokens: system rules and format instructions
~1,000, four retrieved chunks ~600, the rest evidence summaries.

### The headers do not tell you what you need to know

This cost a wasted run on 2026-09-09, so it is worth stating plainly.

`scripts/check_llm.py` reported the endpoint reachable and JSON adherence fine,
and `compare` was started on that basis. It completed four items out of
thirty-two: the previous day had consumed the daily allowance and about 500
tokens were left. The pre-flight had spent roughly 200 tokens, which fit in that
gap, so a green light there proved nothing at all about the 88,000 tokens the
run needed.

The obvious remedy looks like reading the rate-limit headers. It is not, because
of how the buckets are labelled. Measured against Groq:

| Header | What it actually tracks |
|---|---|
| `x-ratelimit-limit-tokens` = 8000 | tokens per **minute** |
| `x-ratelimit-remaining-tokens` = 7927 | remaining **this minute** |
| `x-ratelimit-limit-requests` = 1000 | requests per **day** |
| `x-ratelimit-remaining-requests` = 998 | remaining **today** |

The token headers are the per-minute bucket and the request headers are the
per-day bucket. **Tokens per day - the limit that stops a long evaluation - is
in no header.** At the moment the account stood at 199,519 of 200,000 for the
day, `x-ratelimit-remaining-tokens` read 7,789.

The daily figure is published in exactly one place: the body of a 429.

```
on tokens per day (TPD): Limit 200000, Used 199519, Requested 3034
```

So `app/eval/quota.py` captures it there. Every rate-limit refusal during a run
records the provider's own daily numbers to `data/eval/quota_state.json`, and
the pre-flight reports that reading with its age. Sections 5 and 6 of
`python scripts/check_llm.py` show the headers and the daily allowance
separately, and the script now **exits 2** when the allowance cannot cover a
`compare` run, so it can gate a script rather than merely be read.

If nothing has been recorded yet the pre-flight says the daily allowance is
*unknown* and declines to give a green light. That is deliberate: the original
mistake was treating an absence of evidence as headroom.


**Groq free tier** for `openai/gpt-oss-120b` is roughly 30 requests/min,
1,000 requests/day, 8,000 tokens/min, 200,000 tokens/day. Against the table
above, the daily token cap is the binding constraint, not the request cap:

- `compare` alone is ~135K tokens and **fits in one day**.
- `ablation` is ~400K more and therefore needs **two to three more days**.

This is workable because **the cache makes the run resumable**. Responses are
stored by input hash, so re-running the same command on a later day skips
everything already answered and continues where the quota cut it off. Just run
the command again the next day.

Two things that reduce the bill:

1. **Run `compare` before `ablation`.** The ablation's `full` configuration is
   byte-identical to `llm_full`, and both use the cache tag `llm_full:111`, so
   `compare` pre-pays 70 of the ablation's 350 requests.
2. **Run one ablation configuration at a time** if you want to stay under the
   daily cap deliberately rather than by hitting an error:

   ```bash
   python -m app.eval.ablation --dataset synthetic --configs no_rag
   python -m app.eval.ablation --dataset synthetic --configs no_questionnaire
   ```

**If the multi-day wait is unattractive, use Ollama instead.** There is no quota,
the whole batch runs in one sitting, and because nothing leaves your machine the
consent question disappears entirely. The trade-off is that a locally-hosted
small model follows strict JSON less reliably, so watch the parse-failure count
below.

---

## Step 5 — Run the evaluations

```bash
python -m app.eval.compare  --dataset synthetic   # ~140 requests
python -m app.eval.ablation --dataset synthetic   # ~350 requests
python -m app.eval.evaluate                       # no API calls
```

Artifacts land in `data/eval/`: `comparison.csv`, `comparison.md`,
`confusion_*.png`, `ablation.csv`, `ablation.md`, `ablation.png`.

### Before you trust any number, check the parse rate

`llm_zeroshot` must return strict JSON. Weaker free models often do not, and on
a parse failure the harness **falls back to predicting `Moderate`** and counts
the failure. A model failing 30 % of the time produces a metric that looks
plausible and means nothing.

```bash
grep parse_failures data/eval/comparison.csv
```

Rule of thumb: a handful out of 70 is tolerable and should be reported. Tens of
failures means the model cannot follow the format, and you should switch model
rather than report the number.

---

## Step 6 — Fold the results into the report

1. Replace the `[TBD-EXPERIMENT]` markers in Table 4.3 and Table 4.6.
2. State the model and provider you used, in §4.4 and the abstract.
3. Report `parse_failures` alongside the `llm_zeroshot` row.
4. Update §6.1 O2 and O3 from partially achieved.
5. Keep the existing caveat: `llm_full` sees the DASS/PSS scores that define the
   ground-truth label, so its agreement is partly circular. The
   `no_questionnaire` ablation row is the honest text-only comparison.
6. Re-run `python -m app.eval.evaluate` and quote `disagreement_rate` in §5.4.

Remember the standing limitation that no key changes: the text is generated from
41 templates, so these numbers characterise template memorisation, not stress
detection. Only the real-data study fixes that.
