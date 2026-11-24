from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.db.models import Conversation, User
from app.services.conversations import owned_conversation, recent_turns

router = APIRouter(prefix="/conversations", tags=["conversations"])
Session = Annotated[AsyncSession, Depends(get_session)]
Owner = Annotated[User, Depends(get_current_user)]


@router.post("", status_code=201)
async def create_conversation(user: Owner, session: Session):
    chat = Conversation(user_id=user.id)
    session.add(chat)
    await session.flush()
    result = {"id": str(chat.id)}
    await session.commit()
    return result


@router.get("")
async def list_conversations(user: Owner, session: Session):
    rows = await session.scalars(select(Conversation).where(
        Conversation.user_id == user.id
    ).order_by(Conversation.created_at.desc()).limit(100))
    return [{"id": str(chat.id), "created_at": chat.created_at} for chat in rows]


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: UUID, user: Owner, session: Session):
    if not await owned_conversation(session, user.id, conversation_id):
        raise HTTPException(404, "Conversation not found")
    turns = await recent_turns(session, user.id, conversation_id, limit=100)
    return {"id": str(conversation_id), "turns": [
        {"question": turn.question, "answer": turn.answer, "created_at": turn.created_at}
        for turn in turns
    ]}


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: UUID, user: Owner, session: Session):
    chat = await owned_conversation(session, user.id, conversation_id)
    if chat is None:
        raise HTTPException(404, "Conversation not found")
    await session.delete(chat)
    await session.commit()
    return Response(status_code=204)
