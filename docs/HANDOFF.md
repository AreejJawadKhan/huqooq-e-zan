# Huqooq-e-Zan (حقوقِ زن): handoff for the next developer or AI IDE

Written 2026-11-11 at the end of the hackathon build session. Read this first, then `CLAUDE.md`, `docs/API.md`, `README.md`, `docs/PROJECT_CONTEXT.md`.

## 1. What it is
Voice-first, Urdu-first legal-information assistant for women in Pakistan (workplace harassment, minimum/unpaid wages, women's property and inheritance; Punjab first). It answers ONLY from retrieved statute text, cites Act and section, says where to go (helplines), drafts a complaint letter (.docx), and refuses honestly when the law data does not cover a question. Danger and self-harm messages take a deterministic path (no model). It is legal information, not legal advice. SDGs 5, 8, 16. Hackathon: Build with Google (freeze was 2:00 PM, 2026-11-11).

## 2. State: everything merged to `main` (local merge commit `45a160a`; check `git log origin/main` that the push landed)
203 backend tests pass (2 skipped: eval gate waiting for its first baseline); frontend `npm run build` passes.

### Architecture (see README for the diagram)
Browser (React/Vite/TS, `frontend/`) -> FastAPI (`backend/app/`). Pipeline in `pipeline.py`: deterministic danger check (`safety.py`) -> register detection + lexicon (`lexicon.py`) -> analyzer model -> BM25 retrieval (`retrieval.py`) -> composer model -> citation validation -> fixed referrals/caveats/disclaimers from data files. Models via `providers.py` (Gemini, Groq, Anthropic) with per-stage routing and fallbacks.

### Done this session (all on main)
- **Models**: dead names fixed. Defaults: Gemini `gemini-3.5-flash-lite` (analyzer) / `gemini-3.5-flash` (answer); Groq `openai/gpt-oss-20b` / `openai/gpt-oss-120b` (verified live; qwen rejected). Gemini 3.x thinking tokens ate the output budget -> `thinkingBudget:0` + headroom + MAX_TOKENS retry. Per-stage routing: analyzer Groq-first, answer Gemini-first (`DEFAULT_CHAINS`), env overrides `LLM_PROVIDER`, `ANALYZER_PROVIDER`, `ANSWER_PROVIDER`.
- **Visibility**: `FALLBACK USED` warnings, per-provider counters in `/api/health` (`providers.stats`), `make check-models` / `scripts/check_models.py` (one real tool call per model; 429 = rate-limited not dead), `/api/health?deep=1` (needs `HEALTH_DEEP=1`).
- **Eval gate**: `scripts/run_eval.py --pace 15 --save` writes `data/eval_baseline.json` (fingerprints of default models, prompts, retrieval); `tests/test_eval_baseline.py` fails when they change without a rerun. **No baseline recorded yet**: first real eval scored 14/15 but Gemini's free answer quota was exhausted so Groq answered (mixed models), correctly refused by `--save`. Q4 ("Inquiry Committee rejected my complaint") returned not_found on Groq.
- **Safety**: danger detector normalises Arabic/Urdu letter variants and covers self-harm, sexual violence, blackmail, confinement, forced marriage, Roman Urdu threats (`tests/test_safety.py` has must-flag and must-not-flag lists). Self-harm has its own message and helpline list. **Umang Pakistan 0311-7786264 is in `data/referrals.json` with `verified:false`**: a human must call/confirm it (see its `verification_note`).
- **Resilience**: `TRUSTED_PROXY_HOPS` (default 0; set 1 on Cloud Run) so spoofed X-Forwarded-For can't dodge the limit; `MAX_INFLIGHT`, `GLOBAL_RPM`; `REQUEST_DEADLINE_S` (25) via `deadline.py`; answer cache (only `answered` responses); `Pipeline.ask_degraded` answers from law text with no model; `/api/ask` always returns 200 and sets `X-Huqooq-Degraded: busy|deadline|no_model|unavailable`. Demo-cache answers get caveats/helplines/wage refreshed (`refresh_fixed_parts`).
- **Roman Urdu / code-mixed**: `lexicon.py` (Roman Urdu + Urdu script + English loanwords, fuzzy spellings, provinces, out-of-scope cues, `detect_register`), `answer_roman` response field, `urduize()` guarantees `answer_ur` has no Latin letters (needed for TTS), prompts teach code-mixing and gender-neutral phrasing. Frontend: Roman answer first for Roman users, busy-vs-broken notice with Try again, mic language choice (`ur-PK` default / `en-IN`), read-aloud fallback for Roman answers.
- **Legal claims sourced**: Punjab "60 days" cites s.4; unsourced "delays reported" removed; ICT court-status caveat states only what Federal Ombudsman orders record (WP 529/2021; ICA 85/2023; no dates); letter "as amended in 2022" is correct (HRW/Dawn/Tribune/Geo). Scope messages no longer claim tenancy.
- Demo cache: `data/demo_cache.json` has 9/10 entries; the property question WITHOUT a province is missing (quota). `python scripts/build_demo_cache.py` fills only missing entries. Serve with `DEMO_CACHE=1`.

### API contract changes (NOT yet written into docs/API.md: do this first)
Add to `docs/API.md`: `AskResponse.answer_roman` (string, "" unless the user wrote Roman Urdu); `detected.language` values `ur|roman_ur|en|mixed`; `/api/ask` never returns 502 for provider failure: it returns 200 built from law text with header `X-Huqooq-Degraded` (and `X-Huqooq-Cache: hit` on cached answers); per-client limit returns 429 `{"detail":..., "code":"rate_limited"}`. `frontend/src/types.ts` already mirrors `answer_roman`.

## 3. What needs to be done (priority order)
1. Confirm `origin/main` has the merge (`git push origin main` if not); update `docs/API.md` as above; tell the teammate to `git pull`.
2. **Verify Umang number** (call it / read umang.com.pk), set `verified:true`, `source_url`, `as_of`. Verify the other helplines (15, 1043, 1098, 1737, Punjab Ombudsperson) and the Punjab wage (Rs 40,000; Dawn only, gazette not read). Nothing except 1099 is verified.
3. **Run the eval baseline** when Gemini quota is available (or with a paid key): `make check-models`, then `make eval-save` (`.venv/Scripts/python.exe scripts/run_eval.py --pace 15 --save` on Windows; the Makefile uses `.venv/bin`). Commit `data/eval_baseline.json`.
4. Fill the missing demo-cache entry; set `DEMO_CACHE=1` on the demo machine.
5. **Native Urdu / Roman Urdu review** of `frontend/src/strings.ts`, `backend/app/messages.py`, model output samples. Test the mic (`ur-PK` vs `en-IN`) with a real microphone on the demo laptop (untested).
6. Deploy: Dockerfile (non-root, `.dockerignore` excluding `.env` and `data/raw`), Cloud Run + Firebase Hosting; frontend only calls relative `/api` (add an API-base setting or Hosting rewrites; CSP `connect-src 'self'`); set `CORS_ORIGINS`, `TRUSTED_PROXY_HOPS=1`, HSTS and `frame-ancestors` at the edge. Self-host fonts. No CI exists: add GitHub Actions (pytest, npm build, secret scan). Pin Python deps; `.gitattributes` (`* text=auto eol=lf`); Makefile is Unix-only (`.venv/bin`).
7. Known gaps from the review: stemming in retrieval; 26% of sections >1800 chars are truncated for the model and 75% are truncated at 420 chars in the UI under "Exact text of the law" (show full text); no numeric-consistency guard on wage figures; no circuit breaker (a 429'd provider is retried every request); `/docs` public; free-tier Gemini may train on prompts (real users need a paid/no-training tier); lawyer review of letters/caveats.

## 4. The new data files (commit `bc66534`, `data/raw/`) and what to do with them
None are in `data/sources.yaml` yet, so none are indexed. All PDFs have extractable text (no OCR needed). Identified by reading page 1:

| File | What it is | Note |
| --- | --- | --- |
| `2634.pdf` and `2634 (1).pdf` | Punjab Protection of Women against Violence Act 2016 | **byte-identical duplicates**: delete one. Domestic violence: complaint to court, protection/residence/monetary orders |
| `777a.pdf`, `administratoreecaf3b49...pdf`, `administratordf5df7bd...pdf` | Muslim Family Laws Ordinance 1961 (three copies, ~95% similar) | enable exactly ONE. `777a` is longest (17.3k chars) and mentions Punjab; `eecaf` 15.7k federal; `df5d` 11.4k probably incomplete. Compare ss. 4, 6, 7, 9, 10 before choosing. Applies to Muslims |
| `THE WEST PAKISTAN FAMILY COURTS ACT, 1964.pdf` | Family Courts Act | procedure for dissolution, dower, maintenance, custody |
| `THE GUARDIANS AND WARDS ACT, 1890.pdf` | Guardians and Wards Act | custody/guardianship |
| `administrator359d...pdf` | Dowry and Bridal Gifts (Restriction) Act 1976 | |
| `administratorfb32d6...pdf` | Dissolution of Muslim Marriages Act 1939 | khula / grounds for dissolution |
| `2555.pdf`, `2558.pdf` (older) | Punjab Commission on the Status of Women Act 2014; Punjab Fair Representation of Women Act 2014 | institutional/amending: do NOT enable |

Older third-party files in `data/raw` (no licence recorded; the hackathon rules say authorised datasets only; consider removing from git): `Legal_QA_dataset_From_lawyers.csv` (78 Query/Response rows: best used as an EVAL set, after checking its licence), `combined_legal_dataset.csv` (1,474 Query/Response), `Datatset For FAISS.csv` (1,417 rows, Book/Chapter/Section/Heading/Definition), `Muslim_Family_Laws_Ordinance_1961.csv` (11 rows), several CSVs that are not UTF-8 (Limitation Act, CrPC, Police law, Qanun-e-Shahadat, Transfer of property), `train-00000-of-00001.parquet`, `2410.13013v1.pdf` (an arXiv paper), `FOSPAH Laws and Rules.pdf` (federal harassment text: compare ss. 7 and 9 with the ingested Punjab-adapted copy), `property_punjab_2021_duplicate.pdf`.

### Ready-to-paste `data/sources.yaml` entries (keep `enabled: false` until reviewed)
```yaml
  - id: violence_punjab_2016
    act: "Punjab Protection of Women against Violence Act, 2016"
    jurisdiction: punjab
    topic: violence          # NEW topic, see below
    file: 2634.pdf
    enabled: false
    status: opened
    notes: "2634 (1).pdf is an identical copy: delete it."
  - id: mflo_1961
    act: "Muslim Family Laws Ordinance, 1961"
    jurisdiction: pakistan
    topic: family            # NEW topic
    file: 777a.pdf           # alternatives: administratoreecaf3b490e2d43d2e3b50c0c068b5d7.pdf; enable ONE only
    enabled: false
    status: found
    notes: "Three copies; compare ss.4,6,7,9,10. Applies to Muslims only: caveat required."
  - id: dissolution_1939
    act: "Dissolution of Muslim Marriages Act, 1939"
    jurisdiction: pakistan
    topic: family
    file: administratorfb32d6015ae887e6d6b85018961842ea.pdf
    enabled: false
    status: found
  - id: family_courts_1964
    act: "West Pakistan Family Courts Act, 1964"
    jurisdiction: pakistan
    topic: family
    file: "THE WEST PAKISTAN FAMILY COURTS ACT, 1964.pdf"
    enabled: false
    status: found
  - id: guardians_wards_1890
    act: "Guardians and Wards Act, 1890"
    jurisdiction: pakistan
    topic: family
    file: "THE GUARDIANS AND WARDS ACT, 1890.pdf"
    enabled: false
    status: found
  - id: dowry_1976
    act: "Dowry and Bridal Gifts (Restriction) Act, 1976"
    jurisdiction: pakistan
    topic: family
    file: administrator359d2ddc2ad3cb8f4a5bfa3c263e5ba1.pdf
    enabled: false
    status: found
```
Also fix the `property_ict_2020` note in `sources.yaml`: it still says "ruling suspended 16 Mar 2023", which is unverified (the caveat no longer states a date).

### How to turn these into a working feature (the data alone does nothing)
`scripts/ingest.py` skips `enabled: false` and does not validate topics, but retrieval only reaches topics the analyzer can emit. Steps: (1) add the new topics (`family`, `violence`) to `Topic` in `backend/app/schemas.py` AND `frontend/src/types.ts` (one commit, tell the teammate), the analyzer tool enum in `backend/app/llm.py`, `ANALYZER_SYSTEM`/`OUT_OF_SCOPE` texts in `prompts.py`/`messages.py`, `CONCEPTS` in `lexicon.py` (talaq, khula, nafaqa, mehr, custody, jahez, ghar se nikal diya...; remove those words from `OUT_OF_SCOPE_CUES`), referrals topics in `data/referrals.json`, caveats in `messages.caveats_for`, and `letter_type`s if wanted. (2) Enable ONE Ordinance copy, run `make ingest`, read the report (non-contiguous sections = damaged extraction; fix with `data/raw/<name>.txt` plus a regression test). (3) Add eval questions to `tests/test_questions.yaml` (khula, maintenance, custody, dower, domestic violence, Roman Urdu variants), rerun `make eval-save`. (4) Family law is higher stakes: needs a lawyer's review, a "Muslim personal law only" caveat, and Roman-Urdu/Urdu answer review before it is shown to users. (5) `danger`: domestic violence questions should keep the deterministic danger path; add the Punjab 2016 Act as the legal context only after the danger screen.
Also still missing from the original plan: Sindh/KP/Balochistan minimum wage Acts, KP property Act 2019, tenancy Acts (prompts no longer claim tenancy).

## 5. Working rules and gotchas
- `CLAUDE.md`: frontend work on `feat/frontend`, backend/data on `feat/backend-data`; add files by path, never `git add .`; never commit `.env`; contract (`docs/API.md`, `schemas.py`, `types.ts`) changes together; merge to `main` after tests and build pass.
- Windows: use `.venv/Scripts/python.exe`; tests run with `.venv/Scripts/python.exe -m pytest -q`. Conftest blanks provider keys so tests never call real models.
- Never read or print `.env`; the app loads it. Free-tier quotas (Gemini 3.5-flash is tiny) are the main operational risk: build the demo cache early.
- Model names expire: run `make check-models` after any change; the eval gate forces a rerun when defaults or prompts change.
- Verified facts only: nothing is marked `verified:true` unless an official page was read; the UI labels the rest "Not yet verified".
- The Urdu strings were written by an AI and have not been reviewed by a native speaker.
