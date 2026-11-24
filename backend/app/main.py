from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.concurrency import run_in_threadpool
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.routes.auth import router as auth_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.qa import router as qa_router
from app.api.routes.search import router as search_router
from app.core.config import get_settings
from app.core.limits import RateLimiter
from app.core.logging import configure_logging
from app.core.resources import AppResources
from app.core.security import verify_access_token
from app.db.session import database_url
from app.retrieval.embeddings import E5Embeddings, load_model
from app.retrieval.vectors import VectorIndex
from app.services.recovery import fail_stale_ingestions

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.postgres_password is None:
        # Liveness and unauthenticated-route tests do not need external services.
        yield
        return

    engine = create_async_engine(database_url(settings), pool_pre_ping=True)
    client = None
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        client = AsyncQdrantClient(url=settings.qdrant_url, timeout=30)
        embeddings = E5Embeddings()
        index = VectorIndex(client, settings.qdrant_collection, embeddings.dimension)

        if settings.preload_embeddings:
            await run_in_threadpool(load_model)
        await index.ensure_collection()
        await fail_stale_ingestions(settings, engine)

        app.state.resources = AppResources(
            engine=engine,
            sessions=sessions,
            qdrant=client,
            embeddings=embeddings,
            index=index,
        )
        yield
    finally:
        app.state.resources = None
        if client is not None:
            await client.close()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    limiter = RateLimiter()
    app = FastAPI(title="DocuAsk API", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(conversations_router)
    app.include_router(search_router)
    app.include_router(qa_router)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        clear_contextvars()
        request_id = uuid4().hex
        bind_contextvars(request_id=request_id)
        started = perf_counter()
        try:
            path = request.url.path
            peer = request.client.host if request.client else "unknown"
            group = "auth" if path in {"/auth/login", "/auth/register", "/auth/refresh"} else "api"
            identity = peer
            if group == "api" and settings.jwt_secret is not None:
                bearer = request.headers.get("Authorization", "")
                if bearer.startswith("Bearer "):
                    owner = verify_access_token(bearer[7:], settings.jwt_secret)
                    if owner is not None:
                        identity = str(owner)
            limit = settings.auth_rate_limit if group == "auth" else settings.api_rate_limit
            if path not in {"/health", "/ready"} and not limiter.allow((group, identity), limit):
                response = JSONResponse(
                    {"detail": "Too many requests"}, status_code=429,
                    headers={"Retry-After": "60"},
                )
            else:
                response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            if path.startswith(("/auth", "/qa", "/search", "/conversations", "/documents")):
                response.headers["Cache-Control"] = "no-store"
            response.headers["X-Request-ID"] = request_id
            log.info(
                "http_request", method=request.method, path=request.url.path,
                status_code=response.status_code,
                latency_ms=round((perf_counter() - started) * 1000, 3),
            )
            return response
        except Exception:
            log.error("request_failed", method=request.method, latency_ms=round(
                (perf_counter() - started) * 1000, 3
            ))
            raise
        finally:
            clear_contextvars()

    return app


app = create_app()
