from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import verify_access_token
from app.db.models import User
from app.db.session import make_session_factory
from app.services.auth import find_user

bearer = HTTPBearer(auto_error=False)


@lru_cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    return make_session_factory(get_settings())


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or settings.jwt_secret is None:
        raise unauthorized
    user_id = verify_access_token(credentials.credentials, settings.jwt_secret)
    if user_id is None:
        raise unauthorized
    user = await find_user(session, user_id)
    if user is None:
        raise unauthorized
    return user
