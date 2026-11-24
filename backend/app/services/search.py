from uuid import UUID

from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Chunk, Document
from app.retrieval.embeddings import E5Embeddings
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.sparse import lexical_search
from app.retrieval.vectors import Match, VectorIndex


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
    if embeddings is None or index is None:
        raise SearchUnavailable("Search resources are not initialized")
    hybrid = settings.retrieval_mode == "hybrid"
    candidate_limit = min(100, limit * 4) if hybrid else limit
    vector = await embeddings.query(question)
    try:
        hits = await index.search(user_id=user_id, vector=vector, limit=candidate_limit)
        if hybrid:
            dense = await _resolve(session, user_id, hits)
            sparse = await lexical_search(
                session, user_id=user_id, question=question, limit=candidate_limit
            )
            scores = {hit['chunk_id']: hit['score'] for hit in dense}
            missing = [chunk_id for chunk_id in sparse if chunk_id not in scores]
            if missing:
                rescored = await index.search(
                    user_id=user_id, vector=vector, limit=len(missing), chunk_ids=missing
                )
                scores.update({hit.chunk_id: hit.score for hit in rescored})
            ranked = reciprocal_rank_fusion([[hit['chunk_id'] for hit in dense], sparse])
            hits = [Match(chunk_id, scores[chunk_id]) for chunk_id in ranked if chunk_id in scores]
    except (ResponseHandlingException, UnexpectedResponse, OSError) as exc:
        raise SearchUnavailable from exc
    return (await _resolve(session, user_id, hits))[:limit]


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
