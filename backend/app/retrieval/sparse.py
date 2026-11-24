import re
from uuid import UUID

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document
from app.ingestion.text import normalize_arabic


def lexical_terms(question: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[^\W_]+", normalize_arabic(question).lower())))[:64]


async def lexical_search(
    session: AsyncSession, *, user_id: UUID, question: str, limit: int
) -> list[UUID]:
    terms = lexical_terms(question)
    if not terms:
        return []
    config = literal_column("'simple'::regconfig")
    query = func.to_tsquery(config, " | ".join(terms))
    vector = func.to_tsvector(config, Chunk.normalized_text)
    rank = func.ts_rank_cd(vector, query)
    statement = (
        select(Chunk.id)
        .join(Document, (Document.id == Chunk.document_id) & (Document.user_id == Chunk.user_id))
        .where(
            Chunk.user_id == user_id,
            Document.user_id == user_id,
            Document.status == "ready",
            vector.op("@@")(query),
        )
        .order_by(rank.desc(), Chunk.id)
        .limit(limit)
    )
    return list((await session.scalars(statement)).all())
