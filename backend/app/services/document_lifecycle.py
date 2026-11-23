from pathlib import Path
from uuid import UUID

import structlog
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.db.models import Chunk, Document
from app.retrieval.vectors import VectorIndex

log = structlog.get_logger(__name__)


class DocumentNotFound(Exception):
    pass


class DocumentNotRetryable(Exception):
    pass


class DocumentBusy(Exception):
    pass


class VectorCleanupFailed(Exception):
    pass


class FileCleanupFailed(Exception):
    pass


def stored_path(settings: Settings, owner: UUID, document: Document) -> Path:
    root = settings.storage_dir.resolve()
    path = (root / document.storage_key).resolve()
    if not path.is_relative_to(root / str(owner)):
        raise ValueError("Invalid stored document path")
    return path


async def remove_document_vectors(
    settings: Settings, user_id: UUID, document_id: UUID,
    index: VectorIndex | None = None,
) -> None:
    client = index.client if index is not None else AsyncQdrantClient(
        url=settings.qdrant_url, timeout=15
    )
    try:
        collection = index.collection if index is not None else settings.qdrant_collection
        if not await client.collection_exists(collection):
            return
        await client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(filter=models.Filter(must=[
                models.FieldCondition(
                    key="user_id", match=models.MatchValue(value=str(user_id))
                ),
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=str(document_id))
                ),
            ])),
            wait=True,
        )
    except (ResponseHandlingException, UnexpectedResponse, OSError, ValueError) as exc:
        raise VectorCleanupFailed from exc
    finally:
        if index is None:
            await client.close()


async def retry_document(
    session: AsyncSession, *, user_id: UUID, document_id: UUID, settings: Settings,
    index: VectorIndex | None = None,
) -> Document:
    document = await session.scalar(
        select(Document)
        .where(Document.id == document_id, Document.user_id == user_id)
        .with_for_update()
    )
    if document is None:
        raise DocumentNotFound
    if document.status != "failed":
        raise DocumentNotRetryable
    if not stored_path(settings, user_id, document).is_file():
        raise FileCleanupFailed

    await remove_document_vectors(settings, user_id, document_id, index=index)
    await session.execute(
        delete(Chunk).where(Chunk.document_id == document_id, Chunk.user_id == user_id)
    )
    document.status = "queued"
    document.failure_reason = None
    document.status_changed_at = await session.scalar(select(func.now()))
    await session.commit()
    await session.refresh(document)
    return document


async def delete_document(
    session: AsyncSession, *, user_id: UUID, document_id: UUID, settings: Settings,
    index: VectorIndex | None = None,
) -> None:
    document = await session.scalar(
        select(Document)
        .where(Document.id == document_id, Document.user_id == user_id)
        .with_for_update()
    )
    if document is None:
        raise DocumentNotFound
    if document.status == "processing":
        raise DocumentBusy

    path = stored_path(settings, user_id, document)
    await remove_document_vectors(settings, user_id, document_id, index=index)
    await session.delete(document)
    await session.commit()
    try:
        await run_in_threadpool(path.unlink, missing_ok=True)
    except OSError as exc:
        log.exception(
            "document_file_cleanup_failed",
            user_id=str(user_id), document_id=str(document_id),
        )
        raise FileCleanupFailed from exc
