# Huqooq (حقوق): instructions for Claude Code

Voice-first, Urdu-first legal-information assistant for women in Pakistan (workplace harassment, women's property and inheritance, minimum wage; Punjab first). Hackathon: Build with Google, SDGs 5, 8, 16. Freeze 2:00 PM, presentations from 2:30 PM.

## Team split (no shared files)
- **Areej (frontend, you are working with her):** edits only `frontend/`.
- **Teammate (backend and data):** edits `backend/`, `scripts/`, `data/`, `tests/`, `docs/` (except API.md changes, which both must agree).
- Contract between us: `docs/API.md`, `backend/app/schemas.py`, `frontend/src/types.ts`. Change them only together, in one commit, after telling the other person.

## Read first
`docs/FRONTEND_PLAN.md` (screens, states, tasks), `docs/API.md`, `docs/fixtures/*.json`, `frontend/src/types.ts`, `frontend/src/design/tokens.css`, `frontend/src/design/components.css`, `frontend/design-reference/*.html` (open in a browser to see the target look).

## Frontend rules
- Vite + React + TypeScript. Dev proxy sends `/api` to `localhost:8000`. Run: `make dev-frontend`. Check: `cd frontend && npm run build` after every change.
- UI state comes only from `response.status`: `answered`, `not_found`, `out_of_scope`, `danger`.
- `danger`: red `role="alert"` banner with Call 15 button first; never show legal text, citations or the letter button.
- Never show an `answered` response with zero citations (treat it as `not_found`).
- Urdu is primary: Urdu blocks `dir="rtl"`, font `--font-urdu`; English blocks `ltr`. Wrap phone numbers in `dir="ltr"`.
- Wages and phone numbers with `verified: false` must show a visible "Not yet verified" label.
- Use only CSS variables from `tokens.css` and the `hq-*` classes in `components.css`. No new colours. Touch targets at least 48px, text at least 14px, no horizontal scroll at 360px.
- Mock mode: `?mock=1` serves `frontend/public/fixtures/ask_*.json` (copies of `docs/fixtures/`), so the UI works with no backend.
- Ask before adding a dependency.

## Git rules
- Work on `feat/frontend`, never directly on `main`. Commit small and often; add files by path (`git add frontend docs/FRONTEND_PLAN.md`), never `git add .`; never commit `.env` or keys.
- Before push: `git fetch origin && git rebase origin/main`, then `cd frontend && npm run build`.
- Merge to `main` only at the agreed times (12:45, 1:30, 2:00 freeze), after build passes and the teammate knows.
- Never `git push --force` or `git reset --hard` without asking.
