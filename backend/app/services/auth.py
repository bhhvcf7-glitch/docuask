from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, password_matches
from app.db.models import User


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    user = User(email=email, password_hash=await hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if await session.scalar(select(User.id).where(User.email == email)) is not None:
            raise EmailAlreadyRegistered from exc
        raise
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not await password_matches(user.password_hash, password):
        raise InvalidCredentials
    return user


async def find_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)
