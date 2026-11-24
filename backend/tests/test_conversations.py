import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.db.models import Conversation, ConversationTurn, User
from app.db.session import database_url
from app.services.conversations import owned_conversation, recent_turns, rewrite_question


@pytest.mark.asyncio
async def test_rewrite_uses_only_prior_questions():
    class Provider:
        async def stream(self, messages):
            assert "previous question" in messages[1]["content"]
            assert "old answer" not in messages[1]["content"]
            yield "What is the cost of the previous project?"
    assert await rewrite_question(
        Provider(), "How much?",
        [SimpleNamespace(question="previous question", answer="old answer")],
    ) == "What is the cost of the previous project?"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL")
async def test_conversation_owner_isolation():
    engine = create_async_engine(database_url(Settings(_env_file=None)))
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                async with AsyncSession(bind=conn) as session:
                    alice, bob, chat = uuid4(), uuid4(), uuid4()
                    session.add_all([
                        User(id=alice, email=f"{alice}@example.com", password_hash="hash"),
                        User(id=bob, email=f"{bob}@example.com", password_hash="hash"),
                    ])
                    await session.flush()
                    session.add(Conversation(id=chat, user_id=alice))
                    await session.flush()
                    session.add(ConversationTurn(
                        conversation_id=chat, question="سؤال", answer="جواب [1]"
                    ))
                    await session.flush()
                    assert await owned_conversation(session, alice, chat)
                    assert await owned_conversation(session, bob, chat) is None
                    assert len(await recent_turns(session, alice, chat)) == 1
                    assert await recent_turns(session, bob, chat) == []
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
