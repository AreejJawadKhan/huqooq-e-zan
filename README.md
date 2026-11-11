# Huqooq-e-Zan (حقوقِ زن)

**A voice-first, Urdu-first legal-information assistant for women in Pakistan.**
Ask in Urdu, Roman Urdu, English, or the mix most people actually speak. Huqooq-e-Zan explains what the law says on
**workplace harassment**, **minimum and unpaid wages**, and **women's property and inheritance rights**, cites the exact
Act and section, tells you where to go, and drafts a complaint letter.

Live demo: https://huqooq.pages.dev · SDG 5 (gender equality) · SDG 8 (decent work) · SDG 16 (access to justice) ·
Built for Build with Google (GDGoC CUI, FA'26).

> **It is legal information, not legal advice.** It answers only from statute text it holds, never predicts the outcome
> of a case, and says "I could not find this" instead of guessing.

## What makes it different

| Principle | How it is enforced |
| --- | --- |
| **Grounded, never guessed** | Answers are written only from retrieved statute sections. The model must cite section ids; citations are validated against what was retrieved. An answer with no valid citation becomes "not found". |
| **Safety first, no model needed** | A deterministic detector (English, Urdu, Roman Urdu, Arabic-keyboard Urdu) catches violence, self-harm, sexual violence, blackmail and confinement *before* any model call and shows helplines instead of legal text. Self-harm has its own message and line. |
| **Speaks the way people speak** | A lexicon understands Roman Urdu, Urdu script and English loanwords with spelling variants (`tankhwah`, `tankha`, `تنخواہ`). Roman Urdu in, Roman Urdu out. The Urdu-script answer is guaranteed free of Latin letters so text-to-speech reads it properly. |
| **Works when the models do not** | Free model tiers get rate-limited. Requests have a deadline, global caps and a cache. If no model can answer, the app still returns the best-matching law text plus helplines (HTTP 200, flagged `X-Huqooq-Degraded`) and the UI says "busy" rather than "broken". |
| **Honest about what is verified** | Wages and helplines carry a `verified` flag; the UI shows "Not yet verified" otherwise. Caveats state only what a source supports. |
| **Fixed text where it matters** | Refusals, helplines, caveats and disclaimers come from data files you control, never from the model. |

## How an answer is produced

```
question (typed or spoken)
 1. safety.py     deterministic danger / self-harm check            -> helplines, no model call
 2. lexicon.py    register (Urdu / Roman / English / mixed), topic, province hints, English search words
 3. analyze       small model: English query, legal search terms, topic, province, scope
                  out of scope / prediction / harmful               -> fixed refusal
 4. retrieve      BM25 over statute sections, filtered by topic and province; wages from data/wages.json
                  nothing relevant                                  -> fixed "not found" + referrals
 5. compose       stronger model: grounded Urdu + English (+ Roman Urdu) answer citing excerpt ids
                  invalid or missing citations                      -> "not found"
 6. fixed parts   referrals, caveats, wage figure and disclaimers are added from data files
 *  any model failure, deadline or cap: ask_degraded() answers from the law text alone, no model
```

## Stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI. Rate limit, global admission caps, per-request deadline, answer cache. |
| Retrieval | BM25 (`rank-bm25`) over section-level chunks (no model download) |
| Models | Gemini and Groq (free tiers), Anthropic optional. **Per-stage routing:** the analyzer runs Groq first (about 1 s), the answer runs Gemini first (best Urdu); each falls back to the other. Forced tool calls give structured JSON. |
| Letters | `python-docx` templates: instant, predictable, no model call |
| Frontend | Vite + React + TypeScript, bilingual RTL/LTR layout, mock mode (`?mock=1`) |
| Voice | Browser Web Speech API with an Urdu / Roman-English choice, read-aloud for answers, typed fallback |
| Hosting | Cloudflare Pages (static site + `/api` proxy function) in front of the FastAPI backend (see `docs/DEPLOY.md`) |

## Quick start

```bash
make setup                 # venv, Python deps, npm install, creates .env
# put a GEMINI_API_KEY and/or GROQ_API_KEY in .env
make ingest                # builds data/processed/chunks.jsonl and prints a report
make dev-backend           # http://127.0.0.1:8000
make dev-frontend          # http://localhost:5173 (second terminal)
make test                  # offline tests, no API key needed
make check-models          # one real call per configured model: catches retired model names
make eval                  # the 15 acceptance questions against the real models
make eval-save             # record data/eval_baseline.json (the eval gate)
make demo-cache            # pre-compute answers for the rehearsed demo questions
```

The Makefile uses `.venv/bin`. On Windows run the same commands directly, for example
`.venv\Scripts\python.exe -m pytest -q` and `.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000`.

Check `http://127.0.0.1:8000/api/health`: `chunks_indexed` must be above 0. With no frontend you can still use
`?mock=1` to see every UI state.

## What it covers today

| Topic | Sources (enabled) | Jurisdiction |
| --- | --- | --- |
| Workplace harassment | Protection against Harassment of Women at the Workplace Act, 2010 (amended 2022) | Pakistan |
| Women's property | Punjab Enforcement of Women's Property Rights Act, 2021; Islamabad Act, 2020 (court-challenged: caveat shown) | Punjab, ICT |
| Wages | Punjab Minimum Wages Act, 2019; Payment of Wages Act, 1936. Rates per province in `data/wages.json` | Punjab, Pakistan |

**Not covered yet** (answered with a polite refusal): divorce and khula, maintenance and mehr, custody, dowry,
domestic violence, tenancy. The law files for several of these are already in `data/raw/`; the steps to turn them into a
working feature are in `docs/HANDOFF.md`.

## Repo map

```
backend/app/   main.py (routes, rate limit, admission, cache)  pipeline.py (the flow above)
               llm.py + prompts.py (model layer)  providers.py (Gemini/Groq/Anthropic, routing, health)
               lexicon.py (Roman Urdu / mixed language)  safety.py (danger detection)
               retrieval.py  limits.py  deadline.py  data.py  messages.py (fixed text)  letters.py
data/          sources.yaml (manifest)  wages.json  referrals.json  demo_cache.json  raw/ (PDFs)  processed/ (chunks)
scripts/       ingest.py  run_eval.py  check_models.py  build_demo_cache.py
tests/         offline tests with a fake model; test_questions.yaml = the 15 acceptance questions
frontend/      Vite app (src/, public/fixtures, functions/api = Cloudflare proxy, wrangler.toml)
docs/          API.md (frontend/backend contract)  DEPLOY.md  EVAL.md  HANDOFF.md  SUBMISSION.md
```

## Configuration

Copy `.env.example` to `.env`. The ones that matter:

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` | At least one. Providers without a key are skipped. |
| `LLM_PROVIDER`, `ANALYZER_PROVIDER`, `ANSWER_PROVIDER`, `LLM_FALLBACK` | Override the default per-stage routing. |
| `GEMINI_ANALYZER_MODEL`, `GROQ_ANSWER_MODEL`, ... | Override model names. |
| `DEMO_CACHE=1` | Serve pre-computed answers for rehearsed questions (survives a rate-limited free tier). |
| `MIN_SCORE`, `TOP_K` | Retrieval tuning. |
| `MAX_INFLIGHT`, `GLOBAL_RPM`, `REQUEST_DEADLINE_S`, `ANSWER_CACHE_TTL_S` | Quota protection and timeouts. |
| `TRUSTED_PROXY_HOPS`, `PROXY_SECRET` | Client-IP trust behind a proxy (see `docs/DEPLOY.md`). |
| `CORS_ORIGINS`, `DEBUG`, `HEALTH_DEEP` | Origins, debug endpoints (also enables `/docs`), live model health check. |

### Model names expire: check them

Providers retire model names without warning (Gemini 2.5 and Groq Llama 3.x both disappeared). Safeguards:

1. `make check-models` makes one real tool call per configured model (being *listed* proves nothing). HTTP 429 is
   reported as "rate-limited", not "dead".
2. `GET /api/health` shows the provider order and model per stage plus live counters (`ok`, `fail`,
   `served_as_fallback`, `last_error`). A `FALLBACK USED` warning is logged whenever a fallback serves a request.
3. **Eval gate:** `data/eval_baseline.json` records the 15-question result with fingerprints of the default models,
   prompts and retrieval settings. `tests/test_eval_baseline.py` fails if any of them change without a new
   `make eval-save`. (Skipped until the first baseline is committed.)

## Data: the part that decides quality

1. Each source in `data/sources.yaml` with `enabled: true` must exist in `data/raw/` under its `file` name.
2. Run `make ingest` and read the report. Non-contiguous section numbers or very short sections mean damaged PDF
   extraction: save a corrected `<same-name>.txt` in `data/raw/` (it wins over the PDF) and add a test.
3. Never enable two copies of the same Act, or answers cite duplicates.
4. `data/wages.json` and `data/referrals.json` are hand-maintained. Set `verified: true` only after reading the
   official notification or confirming a number on an official page, and keep `source_url` honest.

## Before a demo or launch

- Native Urdu and Roman Urdu review of `frontend/src/strings.ts`, `backend/app/messages.py` and sample answers.
- Lawyer review of the letter templates and caveats. Confirm the Islamabad Act's current court status.
- Confirm every helpline and wage figure, including the Umang self-harm line.
- Run `make check-models`, then `make eval-save`, then `make demo-cache`, and rehearse the voice flow on the demo laptop.
- Use a paid or no-training model tier for real users: free-tier prompts may be used by the provider.

## Known limits

- Retrieval is keyword-based (BM25, no stemming). Paraphrases can miss; add search terms or swap in embeddings behind
  `Retriever.search` (same signature).
- No user data is stored by the app. Questions are sent to the model provider to be answered.
- Urdu and Roman Urdu output has not been reviewed by a native speaker or a lawyer.
- Only the three topics above are covered. Family law (divorce, khula, maintenance, custody) needs a "Muslim personal
  law" caveat and legal review before it is enabled.

## Documentation

`docs/API.md` (contract) · `docs/DEPLOY.md` (Cloudflare) · `docs/EVAL.md` (evaluation) · `docs/HANDOFF.md` (state and
to-do list) · `docs/SUBMISSION.md` (hackathon submission text).
