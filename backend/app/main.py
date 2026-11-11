"""FastAPI app. Run from the repo root:  uvicorn backend.app.main:app --reload --port 8000"""
from __future__ import annotations

import hmac
import io
import logging
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import Settings, get_settings
from .data import ReferralTable, WageTable
from .deadline import request_deadline
from .demo_cache import DemoCache, cache_key
from .limits import Admission, AnswerCache, client_ip
from .safety import detect_danger
from .letters import build_letter
from .pipeline import Pipeline
from .providers import STATS, build_llm, failure_reason, config_fingerprint, describe_stages, prompts_fingerprint, smoke_test
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
        expose_headers=["Content-Disposition", "X-Huqooq-Degraded"],
    )
    app.state.pipeline = pipeline
    demo = DemoCache.load(settings.demo_cache_path) if settings.demo_cache else DemoCache({})
    hits: dict[str, deque] = defaultdict(deque)
    admission = Admission(settings.max_inflight, settings.global_rpm)
    answers = AnswerCache(settings.answer_cache_ttl_s, settings.answer_cache_size)

    @app.get("/")
    def root():
        """Make accidentally opening the API port helpful during local development."""
        return {
            "service": "Huqooq API",
            "status": "ok",
            "frontend": "http://127.0.0.1:5173/",
            "api_health": "/api/health",
        }

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method == "POST" and request.url.path in _RATE_PATHS:
            # X-Forwarded-For is only trusted for the hops our own proxies add (TRUSTED_PROXY_HOPS); by default the
            # socket address is used, so a spoofed header cannot reset the limit.
            who = None
            if settings.proxy_secret and hmac.compare_digest(request.headers.get("x-huqooq-proxy-key", ""), settings.proxy_secret):
                who = request.headers.get("x-huqooq-client-ip", "").strip() or None
            if who is None:
                who = client_ip(
                    request.headers.get("x-forwarded-for", ""),
                    request.client.host if request.client else "unknown",
                    settings.trusted_proxy_hops,
                )
            now = time.monotonic()
            q = hits[who]
            while q and now - q[0] > RATE_WINDOW_S:
                q.popleft()
            if len(q) >= RATE_LIMIT:
                return JSONResponse({"detail": "Too many requests. Please wait a minute and try again.", "code": "rate_limited"}, status_code=429, headers={"Retry-After": str(RATE_WINDOW_S)})
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

    chunk_count: dict[str, int] = {}
    deep_cache: dict = {"at": 0.0, "rows": []}

    @app.get("/api/health")
    def health(deep: bool = False):
        """Liveness plus a view of the model setup. Cheap by default: nothing here calls a model. `deep=1` (only
        when HEALTH_DEEP=1) makes one tiny real call per configured model, cached for 60 s."""
        if "n" not in chunk_count:  # building the BM25 index is slow: do it once, not on every health check
            chunk_count["n"] = (
                len(app.state.pipeline.retriever) if app.state.pipeline is not None else len(Retriever.from_jsonl(settings.chunks_path))
            )
        n = chunk_count["n"]
        stages = describe_stages(settings)
        body = {
            "status": "ok",
            "chunks_indexed": n,
            "api_key_set": settings.any_llm_key or app.state.pipeline is not None,
            "demo_cache_entries": len(demo),
            "provider": settings.llm_provider if settings.any_llm_key else None,
            "hint": None if n else "No chunks yet: put source files in data/raw and run `make ingest`.",
            "providers": {
                "stages": stages,  # chain and model per stage, in the order they are tried
                "model_config": config_fingerprint(stages),
                "prompts": prompts_fingerprint(),
                # live counters since this process started: ok / fail / served_as_fallback / last_error per provider:stage
                "stats": STATS.snapshot(),
            },
        }
        if deep:
            if not settings.health_deep:
                body["providers"]["deep"] = "disabled: set HEALTH_DEEP=1 to allow live model checks"
            else:
                now = time.monotonic()
                if now - deep_cache["at"] > 60:
                    deep_cache["rows"] = smoke_test(settings)
                    deep_cache["at"] = now
                body["providers"]["deep"] = deep_cache["rows"]
        return body

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest, response: Response):
        """Always answers. If no model can (rate-limited, out of time, no key, at the request cap) the response is built
        from the law text alone and carries `X-Huqooq-Degraded: busy | deadline | no_model | unavailable`, so the UI can
        tell "busy, try again" from "broken" and still show the user something useful."""
        pipeline = get_pipeline()
        # Danger messages always take the deterministic path: no cache, no model, no admission needed.
        if detect_danger(req.question):
            return pipeline.ask(req)

        key = cache_key(req.question, req.jurisdiction)
        if len(demo):
            cached = demo.get(req.question, req.jurisdiction)
            if cached is not None:
                return pipeline.refresh_fixed_parts(cached)
        remembered = answers.get(key)
        if remembered is not None:
            response.headers["X-Huqooq-Cache"] = "hit"
            return remembered

        if not admission.enter():
            response.headers["X-Huqooq-Degraded"] = "busy"
            return pipeline.ask_degraded(req, "busy")
        try:
            with request_deadline(settings.request_deadline_s):
                result = pipeline.ask(req)
            answers.put(key, result)
            return result
        except Exception as exc:  # noqa: BLE001 - never show the provider's error; answer from the law text instead
            reason = failure_reason(exc)
            # Never echo provider errors to the browser (they can contain request details). Log server-side only.
            log.warning("ask degraded (%s): %s", reason, type(exc).__name__)
            log.debug("ask failure detail", exc_info=True)
            response.headers["X-Huqooq-Degraded"] = reason
            return pipeline.ask_degraded(req, reason)
        finally:
            admission.leave()

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
