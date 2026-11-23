from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.core.config import Settings, get_settings
from app.db.models import User
from app.schemas.search import SearchHit, SearchRequest
from app.services.search import SearchUnavailable, search_documents

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[SearchHit])
async def search(
    payload: SearchRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[SearchHit]:
    try:
        hits = await search_documents(
            session,
            user_id=user.id,
            question=payload.question,
            limit=payload.limit,
            settings=settings,
        )
    except SearchUnavailable as exc:
        raise HTTPException(status_code=503, detail="Vector search is unavailable") from exc
    return [SearchHit.model_validate(hit) for hit in hits]
