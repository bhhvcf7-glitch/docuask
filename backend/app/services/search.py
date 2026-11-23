from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Chunk, Document
from app.retrieval.embeddings import E5Embeddings
from app.retrieval.vectors import VectorIndex


class SearchUnavailable(Exception):
    pass


async def search_documents(
    session: AsyncSession,
    *,
    user_id: UUID,
    question: str,
    limit: int,
    settings: Settings,
    embeddings: E5Embeddings | None = None,
    index: VectorIndex | None = None,
) -> list[dict]:
    embedder = embeddings or E5Embeddings()
    vector = await embedder.query(question)
    try:
        if index is None:
            client = AsyncQdrantClient(url=settings.qdrant_url, timeout=20)
            try:
                store = VectorIndex(client, settings.qdrant_collection, embedder.dimension)
                await store.ensure_collection()
                hits = await store.search(user_id=user_id, vector=vector, limit=limit)
            finally:
                await client.close()
        else:
            hits = await index.search(user_id=user_id, vector=vector, limit=limit)
    except (ResponseHandlingException, UnexpectedResponse, OSError) as exc:
        raise SearchUnavailable from exc
    return await _resolve(session, user_id, hits)


async def _resolve(session: AsyncSession, user_id: UUID, hits: list) -> list[dict]:
    if not hits:
        return []
    ids = [hit.chunk_id for hit in hits]
    statement = (
        select(Chunk, Document.original_name)
        .join(
            Document,
            (Document.id == Chunk.document_id) & (Document.user_id == Chunk.user_id),
        )
        .where(
            Chunk.id.in_(ids),
            Chunk.user_id == user_id,
            Document.user_id == user_id,
            Document.status == "ready",
        )
    )
    rows = (await session.execute(statement)).all()
    allowed = {chunk.id: (chunk, name) for chunk, name in rows}
    return [
        {
            "chunk_id": hit.chunk_id,
            "document_id": allowed[hit.chunk_id][0].document_id,
            "filename": allowed[hit.chunk_id][1],
            "page_number": allowed[hit.chunk_id][0].page_number,
            "text": allowed[hit.chunk_id][0].original_text,
            "score": hit.score,
        }
        for hit in hits if hit.chunk_id in allowed
    ]
