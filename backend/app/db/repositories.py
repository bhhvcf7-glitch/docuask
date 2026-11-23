from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document


async def get_document(
    session: AsyncSession, *, user_id: UUID, document_id: UUID
) -> Document | None:
    statement = select(Document).where(
        Document.user_id == user_id, Document.id == document_id
    )
    return await session.scalar(statement)


async def list_document_chunks(
    session: AsyncSession, *, user_id: UUID, document_id: UUID
) -> list[Chunk]:
    statement = (
        select(Chunk)
        .join(
            Document,
            (Chunk.document_id == Document.id) & (Chunk.user_id == Document.user_id),
        )
        .where(Document.user_id == user_id, Document.id == document_id)
        .order_by(Chunk.ordinal)
    )
    return list((await session.scalars(statement)).all())
