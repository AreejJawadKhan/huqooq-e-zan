# Deploying on Cloudflare (about 10 minutes)

Shape: **Cloudflare Pages** serves `frontend/dist` over HTTPS (the browser mic needs HTTPS) and a Pages Function
(`frontend/functions/api/[[path]].js`) proxies `/api/*` to the FastAPI backend, so the app stays same-origin (no CORS, CSP `connect-src 'self'` works).
The Python backend cannot run on Workers (BM25, python-docx), so it runs anywhere that can run the Dockerfile, or on the demo laptop behind a **Cloudflare Tunnel**.

1. Backend `.env`: `GEMINI_API_KEY`/`GROQ_API_KEY`, `DEMO_CACHE=1`, `PROXY_SECRET=<long random string>`, `CORS_ORIGINS` not needed (same-origin).
   Run: `.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000`
2. Tunnel (no account needed for a quick one): `cloudflared tunnel --url http://127.0.0.1:8000` prints `https://<random>.trycloudflare.com`.
   For a stable name use a named tunnel on your domain. The URL is the backend; keep it private.
3. Pages: `cd frontend && npm run build && npx wrangler pages deploy dist --project-name huqooq`
   (first time: `npx wrangler login`, then create the project when asked).
4. Pages project > Settings > Variables and Secrets: `BACKEND_URL=https://<tunnel host>` and `PROXY_SECRET=<same string>`; redeploy once so the function sees them.
5. Check: `https://huqooq.pages.dev/api/health`, then ask a question, then use the mic.
`PROXY_SECRET` lets the proxy pass each visitor's real IP to the backend's rate limiter; without it every visitor shares one 20/min bucket.
Quota is the demo risk: keep `DEMO_CACHE=1` and run `make eval-save` / `scripts/build_demo_cache.py` beforehand.
