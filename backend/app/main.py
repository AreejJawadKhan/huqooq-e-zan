"""FastAPI app. Run from the repo root:  uvicorn backend.app.main:app --reload --port 8000"""
from __future__ import annotations

import io
import logging
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import Settings, get_settings
from .data import ReferralTable, WageTable
from .letters import build_letter
from .pipeline import Pipeline
from .providers import build_llm
from .retrieval import Retriever
from .schemas import AskRequest, AskResponse, LetterRequest, Referral, WageInfo


log = logging.getLogger("huqooq.api")

# Per-client request budget for the model-backed and letter endpoints (protects the free API keys).
RATE_LIMIT = 20
RATE_WINDOW_S = 60
_RATE_PATHS = {"/api/ask", "/api/letter"}


class _NoKeyLLM:
    """Used when no API key is set. Danger messages still work (they never call a model)."""

    def _fail(self, *_a, **_k):
        raise HTTPException(status_code=503, detail="No model API key is set. Add GEMINI_API_KEY or GROQ_API_KEY to .env (see .env.example).")

    analyze = compose = _fail


def build_pipeline(settings: Settings) -> Pipeline:
    llm = build_llm(settings) or _NoKeyLLM()
    return Pipeline(
        llm=llm,
        retriever=Retriever.from_jsonl(settings.chunks_path),
        wages=WageTable(settings.wages_path),
        referrals=ReferralTable(settings.referrals_path),
        settings=settings,
    )


def create_app(pipeline: Optional[Pipeline] = None, settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Huqooq API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Content-Disposition"],
    )
    app.state.pipeline = pipeline
    hits: dict[str, deque] = defaultdict(deque)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method == "POST" and request.url.path in _RATE_PATHS:
            # Behind a proxy set the first X-Forwarded-For hop; otherwise the socket peer.
            fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            who = fwd or (request.client.host if request.client else "unknown")
            now = time.monotonic()
            q = hits[who]
            while q and now - q[0] > RATE_WINDOW_S:
                q.popleft()
            if len(q) >= RATE_LIMIT:
                return JSONResponse({"detail": "Too many requests. Please wait a minute and try again."}, status_code=429, headers={"Retry-After": str(RATE_WINDOW_S)})
            q.append(now)
            if len(hits) > 5000:  # bound memory
                for k in [k for k, v in hits.items() if not v or now - v[-1] > RATE_WINDOW_S]:
                    hits.pop(k, None)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    def get_pipeline() -> Pipeline:
        if app.state.pipeline is None:
            app.state.pipeline = build_pipeline(settings)
        return app.state.pipeline

    @app.get("/api/health")
    def health():
        n = len(Retriever.from_jsonl(settings.chunks_path)) if app.state.pipeline is None else len(app.state.pipeline.retriever)
        return {
            "status": "ok",
            "chunks_indexed": n,
            "api_key_set": settings.any_llm_key or app.state.pipeline is not None,
            "provider": settings.llm_provider if settings.any_llm_key else None,
            "hint": None if n else "No chunks yet: put source files in data/raw and run `make ingest`.",
        }

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest):
        try:
            return get_pipeline().ask(req)
        except HTTPException:
            raise
        except Exception as exc:  # surface model/API failures as a clean 502 for the UI
            # Never echo provider errors to the browser (they can contain request details). Log server-side only.
            log.error("ask failed: %s", type(exc).__name__)
            log.debug("ask failure detail", exc_info=True)
            raise HTTPException(status_code=502, detail="The answer service is temporarily unavailable. Please try again in a moment.") from exc

    @app.post("/api/letter")
    def letter(req: LetterRequest):
        data = build_letter(req)
        filename = f"huqooq_{req.letter_type}.docx"
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/wages", response_model=list[WageInfo])
    def wages():
        return WageTable(settings.wages_path).all()

    @app.get("/api/referrals", response_model=list[Referral])
    def referrals(topic: str = "harassment", jurisdiction: Optional[str] = None, danger: bool = False):
        return ReferralTable(settings.referrals_path).select(topic, jurisdiction, danger=danger, limit=10)

    if settings.debug:

        @app.get("/api/debug/search")
        def debug_search(
            q: str,
            topic: Optional[str] = None,
            jurisdiction: Optional[str] = None,
            k: int = Query(8, ge=1, le=20),
        ):
            r = Retriever.from_jsonl(settings.chunks_path)
            return [
                {"score": round(s, 3), "id": c.id, "act": c.act, "section": c.section, "heading": c.heading}
                for c, s in r.search(q, topic=topic, jurisdiction=jurisdiction, k=k, min_score=0.0)
            ]

    return app


app = create_app()
