from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.clients.llm import ProviderNotConfigured, make_provider
from app.core.config import Settings, get_settings
from app.db.models import User
from app.schemas.qa import QuestionRequest
from app.services.qa import answer_events

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask")
async def ask(
    payload: QuestionRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    try:
        provider = make_provider(settings)
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail="LLM provider is not configured") from exc

    return StreamingResponse(
        answer_events(
            session,
            user_id=user.id,
            question=payload.question,
            limit=payload.limit,
            settings=settings,
            provider=provider,
            disconnect=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
