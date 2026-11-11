# Huqooq-e-Zan (حقوقِ زن): project context, remaining work and improvement plan

Last updated: Wed 11 Nov 2026, 12:30 PKT. Hackathon freeze 2:00 PM, presentations 2:30 PM to 5:30 PM.
Read with `CLAUDE.md` (rules), `docs/API.md` (contract), `docs/FRONTEND_PLAN.md`, `docs/SUBMISSION.md`.

## 1. What it is

**Huqooq-e-Zan** ("the rights of women") is a voice-first, Urdu-first legal-information assistant for women in Pakistan. A woman asks a question by voice or text (Urdu, Roman Urdu or English). The system answers only from statute text it has retrieved, cites the Act and section, says where to go (helplines, Ombudsperson, labour office), and drafts a complaint letter as a Word file. When the law data does not cover the question it says so instead of guessing. Danger messages (violence, self-harm) take a separate deterministic path that shows helplines first and no legal text.

- **Topics (MVP):** workplace harassment; women's property and inheritance enforcement; minimum wage and unpaid wages. Punjab first, Islamabad partly, other provinces shown honestly as "not covered".
- **SDGs:** 5 (gender equality), 8 (decent work), 16 (access to justice).
- **Who:** a factory worker underpaid; a widow denied her share of land; a paralegal or NGO caseworker who needs cited answers fast. Personas are illustrative composites, not interviewed users.
- **It is legal information, not legal advice.** Every answer says so.

### Hackathon constraints (Build with Google, GDGoC COMSATS Islamabad, CUI Tech Fest FA'26)
- Team of two. Dev session 10:30 AM to 3:00 PM; our freeze is 2:00 PM; rehearsal 2:00 to 2:30.
- Judging: implementation completeness 30, problem relevance and SDG fit 20, innovation 20, Google technology 10, UX 10, presentation 10.
- Rules we must meet: disclose AI models used and AI-generated content; do not present unvalidated output as verified; state limitations; protect privacy; only authorised datasets; no previously completed projects. The first commit was at 10:23 AM, before the 10:30 start; this is disclosed in `docs/SUBMISSION.md`.
- $5 Google Cloud credit: claimed (it is not used by the app yet).

## 2. Architecture

```
Browser (React + Vite + TS)                       FastAPI backend (Python)
  AskPanel (text / mic ur-PK) ──POST /api/ask──▶  1 danger check (regex en/ur/Roman Urdu, NO model)
  ResultView (4 states)                           2 analyzer model  → topic, province, English search terms, scope
  LetterDialog ──POST /api/letter──▶ .docx        3 BM25 retrieval over statute sections (min score → refuse)
  SpeakButton (browser Urdu voice)                4 composer model  → Urdu + English answer that MUST cite section ids
  ?mock=1 → /public/fixtures/*.json               5 citation check  → drop unretrieved ids; uncited → not_found
                                                  6 referrals, wages, caveats, disclaimers from data files (never the model)
                                                  Model providers: Gemini (default) → Groq → Anthropic (per-call fallback)
```

**Safety invariants (never weaken; each has a test):**
1. The danger check runs before any model call and works with no API key.
2. An answer with no valid citation becomes `not_found`; citations the model invents are dropped.
3. Referrals, wage figures, caveats and disclaimers come from `data/*.json` and `backend/app/messages.py`, never from a model.
4. Never invent section numbers, phone numbers or wage figures; anything unverified is labelled "Not yet verified" in the UI.
5. Weak retrieval returns a fixed not-found message; the composer model is not called.

**Design choices:** BM25 not embeddings (a few hundred sections, the analyzer already translates to English legal keywords, no model download); forced tool/function calls for structured output; provider layer behind one interface with fallback and one retry on 429/503; stateless API (no database, no stored conversations).

### Repo layout
```
backend/app/   main.py (routes, rate limit, headers, demo cache) pipeline.py safety.py retrieval.py llm.py providers.py
               prompts.py messages.py letters.py config.py data.py demo_cache.py schemas.py
scripts/       ingest.py (PDF → sections → data/processed/chunks.jsonl)  run_eval.py  build_demo_cache.py
data/          sources.yaml  raw/ (statute PDFs)  processed/chunks.jsonl (tracked)  wages.json  referrals.json  demo_questions.yaml
tests/         64 offline tests + test_questions.yaml (15 acceptance questions)
frontend/      src/{App.tsx,api.ts,types.ts,strings.ts,components/*,design/{tokens.css,components.css}}  design-reference/  public/fixtures/
docs/          API.md  FRONTEND_PLAN.md  SUBMISSION.md  PROJECT_CONTEXT.md  fixtures/
```
Commands: `make setup | ingest | dev-backend | dev-frontend | test | eval | demo-cache`.

### API contract (full detail in `docs/API.md`)
`POST /api/ask {question, jurisdiction?}` → `status` (answered | not_found | out_of_scope | danger), `answer_ur/en`, `citations[]`, `where_to_go[]`, `wage`, `caveats[]`, `needs_province`, `letter_type`, `detected`, disclaimers. `POST /api/letter` → `.docx`. `GET /api/health | /api/wages | /api/referrals`. `GET /api/debug/search` only when `DEBUG=1`. Rate limit 20 requests/minute per client on ask and letter.

### Configuration (`.env`, never committed)
`GEMINI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` (any one is enough); `LLM_PROVIDER`, `LLM_FALLBACK`; model overrides `<PROVIDER>_ANALYZER_MODEL` / `<PROVIDER>_ANSWER_MODEL`; `MIN_SCORE` (default 1.0), `TOP_K` (5); `DEBUG`; `DEMO_CACHE`; `CORS_ORIGINS`.

## 3. Current state (honest)

| Area | State |
| --- | --- |
| Backend pipeline, providers, retrieval, letters | Done; 64 offline tests pass |
| Statute data | Ingested: harassment Act (14 sections incl. Schedule), Punjab property 2021 (12), ICT property 2020 (12), Punjab Minimum Wages Act 2019 (23), Payment of Wages Act 1936 (23); 133 chunks |
| Hardening | Merged to `main` (input bounds, rate limit, headers, CORS, no error leakage) |
| Demo cache | On `feat/backend-data` (not yet merged), plus control-character fix for letters |
| Frontend | F1 to F4 done on `feat/frontend` (not yet merged): shell, mock mode, voice input, four states, sources panel, read-aloud, letter dialog, rebrand |
| Design system | Updated artifact (violet/gold, Huqooq-e-Zan) |
| **Real model calls** | **Never run.** Keys are now saved on the user's machine, not in the cloud sandbox. Default model names (Gemini `gemini-2.5-flash-lite` / `gemini-2.5-flash`; Groq `llama-3.1-8b-instant` / `llama-3.3-70b-versatile`) are unverified |
| Eval | Not run. 15 acceptance questions exist; target 12 of 15 |
| Data verification | Verified: helpline 1099 (mohr.gov.pk). Everything else unverified, including the Punjab Rs 40,000 wage (reported by Dawn, ProPakistani, Dunya, WageIndicator; gazette text not read) |
| Urdu text | UI strings and `messages.py` written by Claude; no native-speaker review yet |

### Known issues and risks
- **Harassment text is the Punjab-adapted copy** (mentions the Governor). The federal text is in `data/raw/FOSPAH Laws and Rules.pdf`. Compare ss. 7 and 9. The 2022 amendment may not be reflected.
- **Islamabad property Act** was challenged in court (IHC WP 529/2021; suspended by a Division Bench in 2023; current status unknown). The caveat must stay visible.
- **Punjab minimum-wage start date** differs between sources (1 Jul 2025 vs Sep 2025).
- **Payment of Wages Act 1936** is the old federal text; provinces have their own versions. Do not present it as the Punjab law.
- **Free-tier privacy:** Gemini free tier may use prompts to improve Google products. Demo with synthetic questions only; our "we do not store" line is true for us, not for the provider.
- **Browser Urdu speech:** recognition (`ur-PK`) and Urdu text-to-speech vary by browser and device; the mic and listen buttons hide themselves when unsupported.
- **Rate limiter** trusts `X-Forwarded-For` blindly and is per-process memory; fine for a demo, spoofable in production (see improvements).
- Two files named `.../2555, 2558, 2634` (other Punjab women's Acts) are intentionally not ingested.

## 4. Remaining implementation tasks (in order; now 12:30, freeze 2:00)

| # | Task | Owner | Time | Done when |
| --- | --- | --- | --- | --- |
| R1 | Pull `main`; `make setup`; `.env` has keys; `make test`; `make dev-backend`; real call to each provider. If a model name is rejected, set `*_ANSWER_MODEL` / `*_ANALYZER_MODEL` in `.env`. | Backend | 12:30 to 12:45 | `/api/health` shows a provider; a real cited answer returns |
| R2 | Merge branches: `feat/backend-data` (demo cache, letter fix) and `feat/frontend` into `main` (tests and `npm run build` green, tell each other first) | Both | 12:45 | `main` builds and tests pass |
| R3 | Integration: run frontend without `?mock=1` against the real backend; fix every difference vs the fixtures | Frontend | 12:45 to 1:15 | All demo questions render correctly end to end |
| R4 | `make eval` with Gemini then Groq; read each failure; tune `prompts.py`, `MIN_SCORE`, `TOP_K`; write `docs/EVAL.md`; choose the default provider | Backend | 12:45 to 1:30 | At least 12 of 15 pass; no uncited answer; all danger and refusal cases pass |
| R5 | Spot-check ingest: five sections per Act against the PDF; fix bad text as `data/raw/<name>.txt` with a regression test; compare harassment ss. 7 and 9 with the federal text | Backend | 12:45 to 1:15 | Section text matches PDFs |
| R6 | Verify numbers on official pages: helplines 15, 1043, 1737, 1098, Punjab Ombudsperson; Punjab wage from the gazette. Set `verified` and `as_of` only for what is confirmed; delete what fails | Either | 1:00 to 1:30 | Every number in the demo is verified with a date or labelled unverified |
| R7 | Urdu review of `frontend/src/strings.ts`, `backend/app/messages.py` and five sample answers by a native speaker | Either | 1:00 to 1:30 | Approved or corrected |
| R8 | `make demo-cache`, set `DEMO_CACHE=1`, test with the network off | Backend | 1:15 to 1:40 | Rehearsed questions answer in under 5 seconds |
| R9 | Deploy a public link (judges like a live URL): backend to Cloud Run, frontend to Firebase Hosting, or the simplest option that works; set `CORS_ORIGINS`; check the CSP | Either | 1:15 to 1:50 | Public link works on a phone |
| R10 | Update `docs/SUBMISSION.md` (name Huqooq-e-Zan, real eval numbers, models actually used, limitations); finalise the problem statement | Backend | 1:30 to 2:00 | Matches reality |
| R11 | Merge, tag and freeze at 2:00; only crash fixes after | Both | 2:00 | Clean clone builds with `make setup` |
| R12 | Rehearse the 2-minute demo three times; record a backup video | Both | 2:00 to 2:30 | Three clean runs; recording saved |

**Demo script:** problem in one line; ask in Urdu by voice (harassment) and show the cited answer and referrals; wage question with the verified-or-unverified label; a danger sentence shows the safety screen; an uncovered question shows honest "not found"; draft the complaint letter and open it in Word; close with models used, limits and privacy.

## 5. Additions and improvements

Rated **Now** (before freeze, high value for low effort), **Soon** (this week), **Later**.

### Business logic and legal accuracy
- **Now: deterministic wage check.** If the user states a salary ("I earn Rs 30,000 in Karachi"), compare it to the stored minimum in code, not by the model, and show the figure with its verified label. Acceptance question 6 needs this.
- **Now: numeric consistency guard.** Reject or flag any answer containing a number (days, rupees, years) that does not appear in a cited excerpt or in `wages.json`. Cheap and catches a classic hallucination.
- **Now: data freshness.** Show "law data last updated <date>" in the footer, and a script that warns when a wage `as_of` is older than 90 days.
- **Soon: correct law per place.** Route harassment questions to the federal text for federal institutions and the Punjab-adapted text for Punjab establishments; show which one applied.
- **Soon: time limits and "what to bring".** A small, data-driven checklist per topic (deadlines such as the 30-day inquiry and appeal windows, documents, where to file) drawn from the cited sections, not from the model.
- **Soon: clarifying follow-up.** When a province or key fact is missing, ask one question (the province prompt already does this) and keep history client-side only.
- **Later: more laws and provinces** (Sindh, KP, Balochistan wage acts; domestic workers; tenancy), and Sindhi/Pashto.

### Backend and architecture
- **Now: trust-proxy flag.** Use `X-Forwarded-For` only when `TRUST_PROXY=1`; otherwise anyone can spoof the header to dodge the rate limit.
- **Now: provider timeouts and clear errors.** Confirm httpx timeouts on every provider call; return 503 with a friendly message and `Retry-After` for rate-limit exhaustion (not a generic 502).
- **Now: Dockerfile** for the backend (needed for Cloud Run) with a non-root user and `.dockerignore` so `.env` and `data/raw` never enter the image.
- **Soon: structured logging without personal data**, request IDs, latency, provider used, fallback count, status distribution; never log question text.
- **Soon: answer cache** (LRU on normalised question + province) to save free-tier quota beyond the demo set.
- **Soon: hybrid retrieval** (BM25 plus Gemini embeddings) if the eval shows retrieval misses; keep the `Retriever.search` signature.
- **Soon: shared rate-limit store** (Redis or Cloud Run's built-in limits) once there is more than one instance; the current limiter is per process.
- **Soon: circuit breaker** so a failing provider is skipped for 60 seconds instead of retried on every request.
- **Later: separate ingestion pipeline** run in CI with a diff report when a statute changes; version stamp in `chunks.jsonl`.

### Frontend and UX
- **Now: self-host fonts** (or serve with `font-display: swap`) so the page works offline and the CSP needs no Google domains.
- **Now: theme toggle and text-size control.** Dark tokens exist but there is no switch; add a persistent preference using `prefers-color-scheme` as the default.
- **Now: error boundary and a "demo mode" banner** when `?mock=1` or the cache is serving answers, so judges are not misled about live behaviour.
- **Soon: PWA** (installable, offline shell, cached fixtures) for low-connectivity users.
- **Soon: Google Cloud Speech-to-Text and Text-to-Speech** as a reliable Urdu fallback (a small backend endpoint; uses the $5 credit; strong for the Google-technology marks).
- **Soon: share and print** an answer as PDF or a WhatsApp text with citations and no personal data.
- **Soon: tests:** Vitest and Testing Library for components; Playwright e2e that loads each of the six fixtures and checks no console errors, no horizontal scroll at 360px, and 48px targets (the script we used for screenshots can be turned into this).
- **Later:** accessibility audit with axe plus a screen-reader pass (not yet done); Urdu-first onboarding; large-print mode.

### Security and privacy
- **Now: secret hygiene.** Add a pre-commit secret scan (gitleaks) and confirm `.env` is ignored in every worktree; rotate any key that was ever pasted into a chat.
- **Now: server headers at deploy.** `Strict-Transport-Security`, `frame-ancestors 'none'` (the meta CSP cannot set this), and CORS pinned to the real frontend origin.
- **Soon: CI checks:** `pip-audit` and `npm audit` on every push (npm audit is clean today).
- **Soon: prompt-injection tests** in the red-team set (injection inside the question and inside a statute excerpt); keep the rule that user text is data.
- **Soon: privacy statement page** covering what the provider receives, retention (none on our side), and that real users should not type identifying details; move to a paid or no-training model tier before any real users.
- **Later:** abuse monitoring, optional CAPTCHA only if abuse appears, data-processing review for a real launch.

### Code quality and process
- **Now: CI** (GitHub Actions): `make test`, `npm run build`, lint.
- **Now: contract drift guard.** `frontend/src/types.ts` is hand-copied from `schemas.py`; generate it from the FastAPI OpenAPI schema (`openapi-typescript`) or add a test that compares field names. A drifting contract is the most likely integration bug.
- **Soon: ruff and mypy** for Python, ESLint for TypeScript; a `make lint` target; pre-commit hooks.
- **Soon: red-team eval set** of 10 prompts (jailbreaks, forged-document requests, self-harm phrasing, outcome predictions) and 10 Urdu and Roman Urdu questions drawn from the lawyer QA CSV already in `data/raw`; run before every demo build.
- **Soon: remove dead code and tighten docs:** `docs/SUBMISSION.md` still says Huqooq; README provider table should mention the demo cache.

### Features that would impress judges
1. Visible eval scorecard in the pitch (for example "14 of 15 grounded, 0 uncited, 100% danger recall").
2. Spoken Urdu answers (voice in and out).
3. Deterministic wage check with the verified label.
4. A live public URL plus the offline backup video.
5. A "case readiness" card: deadline, documents, where to file, drawn from cited sections.
6. A short responsible-AI panel in the app: models used, what is verified, what is not.
7. Roadmap slide: WhatsApp bot, legal-aid partner hand-off, district-level office finder, Sindhi and Pashto.

### What not to do today
Do not add accounts, a database, case tracking or chat history (privacy and time). Do not add more laws until the three covered topics pass the eval. Do not mark any number verified without reading an official source.
