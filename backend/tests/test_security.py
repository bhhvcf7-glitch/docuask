from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.security import (
    hash_password,
    issue_access_token,
    password_matches,
    verify_access_token,
)

SECRET = SecretStr("not-a-production-secret-value-with-32-chars")


@pytest.mark.asyncio
async def test_argon2_hash_is_salted_and_wrong_password_fails() -> None:
    first = await hash_password("correct-horse-battery")
    second = await hash_password("correct-horse-battery")
    assert first != second
    assert first.startswith("$argon2id$")
    assert await password_matches(first, "correct-horse-battery")
    assert not await password_matches(first, "wrong-password")
    assert not await password_matches("invalid-hash", "correct-horse-battery")


def test_access_token_rejects_tampering_expiry_and_wrong_type() -> None:
    owner = uuid4()
    token = issue_access_token(owner, SECRET, 30)
    assert verify_access_token(token, SECRET) == owner
    assert verify_access_token(token, SecretStr("another-secret-value-with-32-chars")) is None
    expired = jwt.encode(
        {
            "sub": str(owner), "type": "access",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        SECRET.get_secret_value(), algorithm="HS256",
    )
    assert verify_access_token(expired, SECRET) is None
    refresh = jwt.encode(
        {
            "sub": str(owner), "type": "refresh",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        SECRET.get_secret_value(), algorithm="HS256",
    )
    assert verify_access_token(refresh, SECRET) is None


def test_short_jwt_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, jwt_secret="short")
