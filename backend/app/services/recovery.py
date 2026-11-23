from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings
from app.db.models import Document
from app.db.session import database_url

log = structlog.get_logger(__name__)


async def fail_stale_ingestions(
    settings: Settings, engine: AsyncEngine | None = None
) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.stale_processing_minutes)
    owned_engine = engine is None
    if engine is None:
        engine = create_async_engine(database_url(settings), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            changed = await connection.execute(
                update(Document)
                .where(
                    Document.status == "processing",
                    Document.status_changed_at < cutoff,
                )
                .values(
                    status="failed",
                    status_changed_at=func.now(),
                    failure_reason="Processing was interrupted. Retry this document.",
                )
                .returning(Document.id)
            )
            count = len(changed.all())
        if count:
            log.warning("stale_ingestions_failed", count=count)
        return count
    finally:
        if owned_engine:
            await engine.dispose()
