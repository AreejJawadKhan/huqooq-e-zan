"""FastAPI app. Run from the repo root:  uvicorn backend.app.main:app --reload --port 8000"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import Settings, get_settings
from .data import ReferralTable, WageTable
from .letters import build_letter
from .pipeline import Pipeline
from .providers import build_llm
from .retrieval import Retriever
from .schemas import AskRequest, AskResponse, LetterRequest, Referral, WageInfo


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
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    app.state.pipeline = pipeline

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
            raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc

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
