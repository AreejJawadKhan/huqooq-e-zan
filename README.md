# Huqooq (حقوق)

A voice-first, Urdu-first legal-information assistant for Pakistan. It explains what the law says on workplace
harassment, minimum wage and women's property rights, cites the exact section, says where to go, and drafts a
complaint letter. SDG 16 (access to justice), SDG 5 (gender equality), SDG 8 (decent work).

It gives legal information, not legal advice, and it refuses to guess: if the laws it holds do not answer a
question, it says so and points to a helpline.

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | Python 3.11+, FastAPI | Fast to write, typed contract, easy tests |
| Retrieval | BM25 (`rank-bm25`) over section-level chunks | A few hundred sections; no model download; the analyzer translates Urdu questions into English legal keywords |
| Models | Free Gemini or Groq key (paid Anthropic optional): small model for query analysis, stronger model for the grounded answer | Forced tool calls give structured JSON; provider and models are set in `.env`, with automatic fallback |
| Letters | `python-docx` templates | Instant, predictable, no model call |
| Frontend | Vite + React + TypeScript | Zero config, hot reload, `/api` proxied to the backend |
| Voice | Browser Web Speech API (`ur-PK`) with typed fallback | No server cost; test it on the demo machine early |

## Quick start

```bash
make setup                 # venv, Python deps, npm install, creates .env
# put a free GEMINI_API_KEY or GROQ_API_KEY in .env
# download the legal PDFs listed in data/sources.yaml into data/raw/ (see "Data" below)
make ingest                # builds data/processed/chunks.jsonl and prints a report
make dev-backend           # http://localhost:8000  (docs at /docs)
make dev-frontend          # http://localhost:5173  (in a second terminal)
make test                  # offline tests, no API key needed
make eval                  # the 15 acceptance questions against the real models
make check-models          # one real call per configured model: catches retired model names
make eval-save             # eval on the shipped models, records data/eval_baseline.json (the eval gate)
```

Check `http://localhost:8000/api/health`: `chunks_indexed` must be above 0.

## How an answer is produced

```
question
  1. safety.py: deterministic danger check (English, Urdu, Roman Urdu) -> help lines, no model call
  2. analyze (small model): language, English query + legal search terms, topic, province, scope flags
        out of scope / prediction / harmful -> fixed refusal
  3. retrieve: BM25 over statute sections, filtered by topic and province; wages come from data/wages.json
        nothing relevant -> fixed "not found" + referrals (the model is never asked to guess)
  4. compose (stronger model): grounded Urdu + English answer that must cite excerpt ids
        citations are validated against what was retrieved; uncited answers become "not found"
  5. referrals and caveats are added from data files, never by the model
```

Every refusal and every helpline is fixed text or data you control. Only step 2 and 4 use a model.

## Repo map

```
backend/app/     main.py (routes) · pipeline.py (the flow above) · llm.py + prompts.py (model layer)
                 retrieval.py · safety.py · data.py · messages.py (fixed Urdu/English text) · letters.py
data/            sources.yaml (what to download) · wages.json · referrals.json · raw/ (PDFs) · processed/ (chunks)
scripts/         ingest.py · run_eval.py
tests/           offline tests with a fake model + test_questions.yaml (the 15 acceptance questions)
frontend/        Vite app: src/api.ts, src/types.ts, src/App.tsx (starter UI)
docs/API.md      the contract between frontend and backend
```

## Data: the part that decides the quality

1. Download each source in `data/sources.yaml` marked `enabled: true` into `data/raw/` with the exact `file` name.
   Only `harassment_2010_fospah` was opened and read while planning; confirm every other link and prefer the
   official text over a mirror.
2. Run `make ingest` and read the report. A "WARNING: section numbers are not contiguous" or a very short
   section means the PDF extraction is damaged. Fix by saving a corrected `<same-name>.txt` in `data/raw/`; it
   wins over the PDF.
3. Never enable two copies of the same Act (for example both harassment sources) or answers will cite duplicates.
4. Fill the gaps: the provincial Minimum Wages Acts and the Payment of Wages Act were not located. Until they
   are added, unpaid-wage questions (test 15) correctly return "not found".
5. `data/wages.json` and `data/referrals.json` are hand-maintained. Everything is `verified: false` until someone
   reads the official notification or confirms the number on an official page. The UI shows this.

## Tuning

- Too many "not found": lower `MIN_SCORE` in `.env`, or improve the search terms in `ANALYZER_SYSTEM` (`prompts.py`).
- Wrong sections retrieved: set `DEBUG=1` and call `/api/debug/search?q=...&topic=harassment` to see scores.
- Answers too long or too legalistic: edit `ANSWER_SYSTEM` in `prompts.py`. No other code needs to change.

## Before the demo

- Have a native Urdu speaker review every Urdu string in `backend/app/messages.py` and test answers 1 to 15.
- Re-check the Islamabad property Act status (it was challenged in court; the UI shows a caveat).
- Re-verify wage figures and helplines, then set `verified: true` and update `as_of`.
- Rehearse the voice flow on the demo laptop; record a backup video.

## Known limits

- Retrieval is keyword-based. If paraphrased questions miss, add search terms or swap in embeddings behind
  `Retriever.search` (same signature).
- No user data is stored. Questions go to the model API for processing.
- The Urdu strings and the Urdu model output have not been reviewed by a native speaker or a lawyer.

## Choosing a model provider

Put at least one key in `.env`. With two or more keys the app routes each pipeline stage to the provider that suits it:

| Stage | What it does | Default order | Why |
| --- | --- | --- | --- |
| Analyzer | classifies the question, finds the province, writes English search terms | Groq `openai/gpt-oss-20b` -> Gemini `gemini-3.5-flash-lite` | small structured job; Groq answers in about 1 s |
| Answer | writes the grounded Urdu and English answer | Gemini `gemini-3.5-flash` -> Groq `openai/gpt-oss-120b` | best Urdu |

Anthropic (`claude-haiku-5-5` / `claude-sonnet-5-5`, paid) is the last fallback for both stages when `ANTHROPIC_API_KEY` is set. Providers without a key are skipped.

| Provider | Key | Cost | Notes |
| --- | --- | --- | --- |
| Gemini | `GEMINI_API_KEY` ([AI Studio](https://aistudio.google.com/apikey)) | Free tier | Free-tier prompts may be used to improve Google products: demo with synthetic questions only. `gemini-3.5-flash` has a very small free quota. |
| Groq | `GROQ_API_KEY` ([console](https://console.groq.com/keys)) | Free plan | Fast; weaker Urdu (sometimes Latin letters inside Urdu text). |
| Anthropic | `ANTHROPIC_API_KEY` | Paid | Use for real user data. |

Override the routing with `LLM_PROVIDER` (one chain for both stages), `ANALYZER_PROVIDER` / `ANSWER_PROVIDER` (`auto`, `same`, or a provider name) and `LLM_FALLBACK`. Override model names with `GEMINI_ANALYZER_MODEL`, `GROQ_ANSWER_MODEL` and friends (see `.env.example`).

### Model names expire. Do not trust them: check them

Providers retire model names without warning (Gemini 2.5 and Groq Llama 3.x both disappeared, and the dead Groq fallback went unnoticed). Three safeguards:

1. `make check-models` makes one real tool call per configured model (a model being *listed* proves nothing: `gemini-2.5-flash-lite` is listed but returns 404). `--list` shows what each provider offers. HTTP 429 is reported as "rate-limited", not "dead".
2. `GET /api/health` shows the model and provider order per stage, plus live counters per provider and stage (`ok`, `fail`, `served_as_fallback`, `last_error`). Set `HEALTH_DEEP=1` to allow `GET /api/health?deep=1`, which runs the check live (cached for 60 s). Whenever a fallback provider has to serve a request, the log gets a `FALLBACK USED` warning: a dead or struggling primary is visible instead of hidden behind answers that still arrive.
3. **Eval gate.** `data/eval_baseline.json` records the 15-question result together with fingerprints of the default models, the prompts and the retrieval settings. `tests/test_eval_baseline.py` fails when any of them changes without a new `make eval-save`, so a new model or an edited prompt cannot change answers unnoticed. `make eval-save` refuses to record a run in which a fallback provider answered (the result would mix models); on a free tier it paces requests, because a 429 turns into a fallback answer. Until the first baseline is committed the gate is skipped with a loud message.

## Hackathon notes

Built for Build with Google (GDGoC CUI, FA'26). See `docs/SUBMISSION.md` for the title, problem statement, SDG alignment, stack, responsible-AI disclosure and limitations.
