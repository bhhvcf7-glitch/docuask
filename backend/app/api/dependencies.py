from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from app.core.resources import AppResources
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import verify_access_token
from app.db.models import User
from app.services.auth import find_user

bearer = HTTPBearer(auto_error=False)


def get_resources(request: Request) -> AppResources:
    resources = getattr(request.app.state, "resources", None)
    if resources is None:
        raise HTTPException(status_code=503, detail="Application resources are not ready")
    return resources


async def get_session(
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AsyncIterator[AsyncSession]:
    async with resources.sessions() as session:
        yield session


def get_token_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID:
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
    return user_id


async def get_current_user(
    user_id: Annotated[UUID, Depends(get_token_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await find_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=401, detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
