from pathlib import Path
from uuid import UUID

import structlog
from pdfminer.pdfexceptions import PDFException
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.db.models import Chunk, Document
from app.db.session import database_url
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import ExtractionError, extract_pages

log = structlog.get_logger(__name__)


async def ingest_document(document_id: UUID, user_id: UUID, settings: Settings) -> None:
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
                .values(status="processing", failure_reason=None)
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
        except (ExtractionError, PDFException, OSError, ValueError) as exc:
            log.warning(
                "pdf_ingestion_failed",
                document_id=str(document_id),
                error_type=type(exc).__name__,
            )
            async with sessions.begin() as session:
                await session.execute(
                    update(Document)
                    .where(
                        Document.id == document_id,
                        Document.user_id == user_id,
                        Document.status == "processing",
                    )
                    .values(status="failed", failure_reason=str(exc)[:500])
                )
            return

        async with sessions.begin() as session:
            await session.execute(
                delete(Chunk).where(
                    Chunk.document_id == document_id, Chunk.user_id == user_id
                )
            )
            session.add_all([
                Chunk(
                    user_id=user_id,
                    document_id=document_id,
                    ordinal=piece.ordinal,
                    page_number=piece.page_number,
                    original_text=piece.original_text,
                    normalized_text=piece.normalized_text,
                )
                for piece in pieces
            ])
            await session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.user_id == user_id,
                    Document.status == "processing",
                )
                .values(status="ready", failure_reason=None)
            )
        log.info("pdf_ingestion_ready", document_id=str(document_id), chunks=len(pieces))
    finally:
        await engine.dispose()
