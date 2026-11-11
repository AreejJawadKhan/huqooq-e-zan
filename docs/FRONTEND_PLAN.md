# Frontend plan (Workflow A)

Goal: one-page React app where someone asks a question by voice or text and gets one of four clearly different results, Urdu first, calm and trustworthy. Owner: Areej. Folder: `frontend/` only.

Product context: voice-first Urdu legal-information assistant; answers only from retrieved statute text; cites the section; says where to go; drafts a complaint letter; refuses honestly when it cannot answer; danger is its own safe state. See `README.md` and `docs/SUBMISSION.md`.

## Already in the repo
Vite/React/TS starter (`src/App.tsx`, `api.ts`, `types.ts`), design tokens (`src/design/tokens.css`), component styles (`components.css`), one HTML reference per component in `design-reference/`, six sample responses in `docs/fixtures/`.

## Screen (top to bottom)
1. Header: "Huqooq" wordmark and one Urdu line saying what it does.
2. Ask panel: large RTL textarea, mic button, send button, optional province select (Punjab, Sindh, KP, Balochistan, Islamabad, Not sure), three tappable example questions.
3. Result area (replaced on each question): loading, error, or one of four states.
4. Letter dialog (opens from the result).
5. Footer: disclaimer, "AI-generated, check with a lawyer", collapsible "What this covers and its limits", model disclosure ("Answers by Google Gemini; built with help from Claude").

## The four states (decided only by `status`)
| status | Show | Never show |
| --- | --- | --- |
| `danger` | Red banner (`role="alert"`) with Call 15 button first, then `where_to_go` | Legal text, citations, letter button |
| `answered` | `answer_ur` large, `answer_en` beneath, caveats, wage chip if `wage`, citation chips (tap to expand excerpt with Act and section), referrals, letter button if `letter_type`, province prompt if `needs_province` | An answer with zero citations (show as not_found) |
| `not_found` | Calm message in Urdu and English plus referrals | An empty screen |
| `out_of_scope` | What Huqooq covers (three topics) plus referrals | Apologetic or blaming wording |

## Edge cases
Request error 502/503: show `detail` and a Retry button. Over 15 s: keep spinner and say it is still working. Double submit: disable Send while loading. Empty `where_to_go`: hide the section. `wage.verified` false: "Not yet verified". Phone numbers inside RTL text: wrap in `dir="ltr"`. Speech recognition missing or denied: hide mic, keep typing. Long answers: wrap, no horizontal scroll at 360px.

## Tasks (times are today; freeze 2:00 PM)
| ID | Time | Task | Done when |
| --- | --- | --- | --- |
| F0 | 11:30 to 11:45 | Pull, branch `feat/frontend`, `make setup`, `make dev-frontend`, open design-reference files | Starter loads at localhost:5173 |
| F1 | 11:45 to 12:15 | App shell: import tokens/components css, RTL layout, fonts, Header, Footer, example chips. Add mock mode `?mock=1` (copy fixtures to `frontend/public/fixtures/`). | Looks like the reference at 360px and 1280px; `?mock=1` works |
| F2 | 12:15 to 12:45 | Ask flow: textarea, mic (`SpeechRecognition`, `ur-PK`), send, loading and error states, province select, call `ask()` | Typed question shows the raw state in mock mode |
| F3 | 12:45 to 1:30 | Result components: DangerBanner, AnswerCard, CitationChip, CaveatNote, WageChip, ReferralList, province prompt that re-asks with `jurisdiction` | All six fixtures render correctly; danger shows no legal text |
| F4 | 1:30 to 2:00 | Letter dialog (fields from `LetterRequest`, `legal_basis` pre-filled from citations), `.docx` download via `downloadLetter()`, accessibility pass | Letter downloads and opens in Word; tab order sensible |
| F5 | 2:00 to 2:30 | Freeze, rehearse the demo twice with the teammate, record backup video | Three clean runs |

Checkpoints with the teammate: 12:45 first live request to the real backend (check `/api/health`), 1:30 run all demo questions together, 2:00 merge and freeze.

## Prompts for Claude Code (paste one at a time)

**Kickoff**
```text
Read CLAUDE.md, docs/FRONTEND_PLAN.md, docs/API.md, docs/fixtures/*.json, frontend/src/types.ts, frontend/src/design/tokens.css, frontend/src/design/components.css and frontend/design-reference/*.html. Work only in frontend/. Confirm the plan back to me in five lines, then start task F1.
```

**F1**
```text
Task F1. Import tokens.css and components.css in main.tsx. Build the page shell in App.tsx, split into small components under src/components/: Header, Footer (disclaimer, AI disclosure, collapsible limits panel), ExampleChips (3 sample questions). Add mock mode: when the URL has ?mock=1, ask() in src/api.ts returns a JSON file from public/fixtures/ chosen by keywords in the question (danger words -> ask_danger, "wage" -> ask_answered_wage, "province" -> ask_needs_province, "xyz" -> ask_not_found, "cooking" -> ask_out_of_scope, else ask_answered). Copy docs/fixtures/ask_*.json into frontend/public/fixtures/. Match frontend/design-reference visually at 360px and 1280px. Run npm run build.
```

**F2**
```text
Task F2. Build AskPanel: RTL textarea, send button, province select (Punjab, Sindh, KP, Balochistan, Islamabad, Not sure) and MicButton (design-reference/MicButton.html). The mic uses window.SpeechRecognition or webkitSpeechRecognition with lang 'ur-PK', shows the live transcript in the textarea, and is hidden with a one-line hint if unsupported or permission denied. Disable Send while loading; show a spinner with Urdu and English text and after 15 seconds say it is still working; on error show the Error message with a Retry button. Pass the province as jurisdiction. Run npm run build.
```

**F3**
```text
Task F3. Build ResultView that switches on response.status. Components: DangerBanner, AnswerCard, CitationChip (tap to expand the excerpt, shows Act and section), CaveatNote (ur and en), WageChip (amount, as_of, "Not yet verified" if verified is false), ReferralList (tel: link with dir="ltr", Unverified chip when verified is false). If needs_province is true show a province prompt that calls ask() again with the chosen jurisdiction. Treat status answered with empty citations as not_found. Check all six fixtures with ?mock=1 and fix anything that looks off against the design-reference files.
```

**F4**
```text
Task F4. Add LetterDialog opened by a "Draft complaint letter" button when response.letter_type is set. Fields: complainant_name (required), complainant_address, complainant_cnic, respondent_name, respondent_details, city, facts (required, 5 to 6000 chars), relief. Pre-fill legal_basis from the citations as "<act>, s.<section>". Submit with downloadLetter() and show success or the error. Then an accessibility pass: logical tab order, visible focus ring (2px var(--focus)), labels on every input, aria-live on loading, no horizontal scroll at 360px, nothing under 14px text or 48px touch height. Run npm run build.
```

**Integration (12:45)**
```text
The backend is running at localhost:8000. Remove ?mock=1 from the URL and test the six demo questions against the real API. List every place where the real response differs from the fixtures (missing fields, empty arrays, null wage) and fix the UI to handle them. Do not change types.ts without telling me.
```
