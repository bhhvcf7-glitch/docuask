import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings
from app.db.models import Document
from app.db.session import database_url

log = structlog.get_logger(__name__)


async def fail_stale_status(engine: AsyncEngine, *, status: str, minutes: int,
                            reason: str) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
    async with engine.begin() as connection:
        changed = await connection.execute(
            update(Document)
            .where(Document.status == status, Document.status_changed_at < cutoff)
            .values(status="failed", status_changed_at=func.now(), failure_reason=reason)
            .returning(Document.id)
        )
        count = len(changed.all())
    if count:
        log.warning("stale_ingestions_failed", previous_status=status, count=count)
    return count


async def fail_stale_ingestions(
    settings: Settings, engine: AsyncEngine | None = None
) -> int:
    owned_engine = engine is None
    if engine is None:
        engine = create_async_engine(database_url(settings), pool_pre_ping=True)
    try:
        return await fail_stale_status(
            engine, status="processing", minutes=settings.stale_processing_minutes,
            reason="Processing was interrupted. Retry this document.",
        )
    finally:
        if owned_engine:
            await engine.dispose()


async def fail_stale_queued(settings: Settings, engine: AsyncEngine) -> int:
    return await fail_stale_status(
        engine, status="queued", minutes=settings.stale_queued_minutes,
        reason="Document processing did not start. Retry this document.",
    )


async def recovery_loop(settings: Settings, engine: AsyncEngine) -> None:
    while True:
        await asyncio.sleep(settings.recovery_interval_seconds)
        try:
            await fail_stale_queued(settings, engine)
        except (SQLAlchemyError, OSError):
            log.exception("queued_recovery_failed")
