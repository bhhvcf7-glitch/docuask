from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging

log = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="DocuAsk API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        clear_contextvars()
        request_id = uuid4().hex
        bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            log.info(
                "http_request", method=request.method, path=request.url.path,
                status_code=response.status_code,
            )
            return response
        finally:
            clear_contextvars()

    return app


app = create_app()
