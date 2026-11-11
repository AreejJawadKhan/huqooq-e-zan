# Huqooq API contract

Base URL in dev: `http://localhost:8000`. The Vite dev server proxies `/api/*` there, so the frontend calls `/api/...`.
Types live in `backend/app/schemas.py` (source of truth) and `frontend/src/types.ts` (mirror). Change both together.

## POST /api/ask

Request: `{ "question": string, "jurisdiction"?: "punjab" | "sindh" | "kp" | "balochistan" | "ict" | "pakistan" | null }`

Response (`AskResponse`):

| Field | Meaning |
| --- | --- |
| `status` | `answered`, `not_found`, `out_of_scope`, or `danger`. Drives the UI state. |
| `answer_ur`, `answer_en` | The answer. Urdu is the primary display (RTL); English is for the team and judges. |
| `confidence` | `high` / `medium` / `low` / `none`. |
| `citations[]` | Sections actually used: `act`, `section`, `heading`, `excerpt`, `source_url`. Always show these. |
| `where_to_go[]` | Helplines and forums, chosen from `data/referrals.json`. First entries are the most urgent. |
| `wage` | Present for wage questions in a known province. Show `as_of`; if `verified` is false say so. |
| `caveats[]` | Fixed bilingual warnings (`en`, `ur`). Show them near the answer, not in a footer. |
| `needs_province` | True when the answer depends on the province and it is unknown. Prompt for it, then re-ask with `jurisdiction`. |
| `letter_type` | If set, offer the "Draft complaint letter" action. |
| `detected` | `language`, `topic`, `jurisdiction`, `english_query` (useful for a debug panel). |
| `disclaimer_*` | Always render. |

UI states to design for:

1. `danger`: red banner, show `where_to_go` first, no legal text, no letter button.
2. `answered`: Urdu answer, caveats, wage chip if present, citations, referrals, letter button.
3. `not_found` and `out_of_scope`: calm message plus referrals. Never show an empty screen.
4. Request error (HTTP 502/503): `detail` holds a human-readable string.

## POST /api/letter

Request (`LetterRequest`): `letter_type` (`harassment_complaint` | `wage_complaint` | `property_complaint`),
`complainant_name`, `facts` (required) and optional `complainant_address`, `complainant_cnic`, `respondent_name`,
`respondent_details`, `city`, `relief`, `legal_basis[]` (pass the citations as strings).
Response: a `.docx` file download. `downloadLetter()` in `frontend/src/api.ts` handles it.

## GET /api/wages, GET /api/referrals, GET /api/health

- `/api/wages`: all rates with `as_of`, `status`, `verified`.
- `/api/referrals?topic=harassment&jurisdiction=punjab&danger=false`
- `/api/health`: `chunks_indexed` (0 means ingest has not been run) and `api_key_set`.
- `/api/debug/search?q=...&topic=...` exists only when `DEBUG=1`; use it to tune retrieval.
