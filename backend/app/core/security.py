from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi.concurrency import run_in_threadpool
from pydantic import SecretStr

hasher = PasswordHasher()


async def hash_password(password: str) -> str:
    return await run_in_threadpool(hasher.hash, password)


async def password_matches(encoded: str, password: str) -> bool:
    try:
        return await run_in_threadpool(hasher.verify, encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def issue_access_token(user_id: UUID, secret: SecretStr, lifetime_minutes: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": now,
         "exp": now + timedelta(minutes=lifetime_minutes)},
        secret.get_secret_value(),
        algorithm="HS256",
    )


def verify_access_token(token: str, secret: SecretStr) -> UUID | None:
    try:
        claims = jwt.decode(
            token, secret.get_secret_value(), algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp"]},
        )
        if claims.get("type") != "access":
            return None
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, TypeError, ValueError, KeyError):
        return None
