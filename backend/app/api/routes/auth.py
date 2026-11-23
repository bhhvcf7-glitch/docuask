from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.core.config import Settings, get_settings
from app.core.security import issue_access_token
from app.db.models import User
from app.schemas.auth import AccessToken, Credentials, LoginCredentials, UserPublic
from app.services.auth import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    authenticate_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserPublic)
async def register(
    payload: Credentials, session: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    try:
        return await register_user(session, payload.email, payload.password)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(status_code=409, detail="Email is already registered") from exc


@router.post("/login", response_model=AccessToken)
async def login(
    payload: LoginCredentials,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessToken:
    if settings.jwt_secret is None:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    try:
        user = await authenticate_user(session, payload.email, payload.password)
    except InvalidCredentials as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc
    return AccessToken(
        access_token=issue_access_token(
            user.id, settings.jwt_secret, settings.access_token_minutes
        )
    )


@router.get("/me", response_model=UserPublic)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
