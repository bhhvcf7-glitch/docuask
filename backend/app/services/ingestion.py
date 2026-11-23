from uuid import UUID

import structlog
from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.db.models import Chunk, Document
from app.db.session import database_url
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import ExtractionError, extract_pages
from app.retrieval.embeddings import E5Embeddings
from app.retrieval.vectors import VectorIndex

log = structlog.get_logger(__name__)


async def ingest_document(
    document_id: UUID,
    user_id: UUID,
    settings: Settings,
    embeddings: E5Embeddings | None = None,
    index: VectorIndex | None = None,
    sessions: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    # Tests can supply a separate session factory without loading the real model.
    engine = None
    if sessions is None:
        engine = create_async_engine(database_url(settings), pool_pre_ping=True)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            claimed = await session.scalar(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.user_id == user_id,
                    Document.status == "queued",
                )
                .values(status="processing", failure_reason=None, status_changed_at=func.now())
                .returning(Document.storage_key)
            )
            await session.commit()
        if claimed is None:
            return

        try:
            path = (settings.storage_dir.resolve() / claimed).resolve()
            if not path.is_relative_to(settings.storage_dir.resolve()):
                raise ExtractionError("Invalid stored document path")
            pages = await run_in_threadpool(extract_pages, path, max_pages=200)
            pieces = chunk_pages(pages)
            if not pieces:
                raise ExtractionError("PDF has no text to index")

            async with sessions.begin() as session:
                await session.execute(
                    delete(Chunk).where(
                        Chunk.document_id == document_id, Chunk.user_id == user_id
                    )
                )
                chunks = [
                    Chunk(
                        user_id=user_id,
                        document_id=document_id,
                        ordinal=piece.ordinal,
                        page_number=piece.page_number,
                        original_text=piece.original_text,
                        normalized_text=piece.normalized_text,
                    )
                    for piece in pieces
                ]
                session.add_all(chunks)
                await session.flush()

            if embeddings is None or index is None:
                raise RuntimeError("Ingestion resources are not initialized")
            vectors = await embeddings.documents([chunk.normalized_text for chunk in chunks])
            await index.upsert(
                user_id=user_id, document_id=document_id, chunks=chunks, vectors=vectors
            )

            async with sessions.begin() as session:
                await session.execute(
                    update(Document)
                    .where(
                        Document.id == document_id,
                        Document.user_id == user_id,
                        Document.status == "processing",
                    )
                    .values(status="ready", failure_reason=None, status_changed_at=func.now())
                )
            log.info("pdf_ingestion_ready", document_id=str(document_id), chunks=len(chunks))
        except Exception as exc:
            # Unexpected failures must not leave documents permanently processing.
            log.exception("pdf_ingestion_failed", document_id=str(document_id))
            detail = (
                str(exc)[:300] if isinstance(exc, ExtractionError)
                else "Document processing failed. Retry the upload."
            )
            async with sessions.begin() as session:
                await session.execute(
                    update(Document)
                    .where(
                        Document.id == document_id,
                        Document.user_id == user_id,
                        Document.status == "processing",
                    )
                    .values(
                        status="failed", failure_reason=detail, status_changed_at=func.now()
                    )
                )
    finally:
        if engine is not None:
            await engine.dispose()
