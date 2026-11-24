import json
from contextlib import aclosing
from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_resources, get_session
from app.clients.llm import ProviderNotConfigured, ProviderUnavailable, make_provider
from app.core.config import Settings, get_settings
from app.core.resources import AppResources
from app.db.models import ConversationTurn, User
from app.schemas.qa import QuestionRequest
from app.services.conversations import owned_conversation, recent_turns, rewrite_question
from app.services.qa import answer_events, event
from app.services.search import search_documents

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask")
async def ask(
    payload: QuestionRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    resources: Annotated[AppResources, Depends(get_resources)],
) -> StreamingResponse:
    try:
        provider = make_provider(settings)
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail="LLM provider is not configured") from exc

    owner = user.id
    question = payload.question
    if payload.conversation_id is not None:
        if not await owned_conversation(session, owner, payload.conversation_id):
            raise HTTPException(404, "Conversation not found")
        turns = await recent_turns(session, owner, payload.conversation_id)
        # Materialize history before ending the read transaction.
        turns = [SimpleNamespace(question=turn.question) for turn in turns]
        await session.rollback()
        try:
            question = await rewrite_question(provider, question, turns)
        except ProviderUnavailable:
            question = payload.question

    async def retrieve(session, *, user_id, question, limit, settings):
        return await search_documents(
            session, user_id=user_id, question=question, limit=limit,
            settings=settings, embeddings=resources.embeddings, index=resources.index,
        )

    async def stream():
        parts = []
        buffered = []
        async with aclosing(answer_events(
            session,
            user_id=owner,
            question=question,
            limit=payload.limit,
            settings=settings,
            provider=provider,
            disconnect=request.is_disconnected,
            search=retrieve,
        )
            async for item in events:

                if payload.conversation_id is None:
                    yield item
                    continue
                kind = item.splitlines()[0][7:]
                data = json.loads(item.splitlines()[1][6:])
                if kind == "token":
                    parts.append(data["text"])
                if kind in {"token", "citations"}:
                    buffered.append(item)
                    continue
                if kind == "done" and parts:
                    if not await owned_conversation(session, owner, payload.conversation_id):
                        yield event("error", {"message": "Conversation no longer exists"})
                        return
                    session.add(ConversationTurn(
                        conversation_id=payload.conversation_id,
                        question=payload.question, answer="".join(parts),
                    ))
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
                        yield event("error", {"message": "Conversation could not be saved"})
                        return
                    for saved in buffered:
                        yield saved
                yield item

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
