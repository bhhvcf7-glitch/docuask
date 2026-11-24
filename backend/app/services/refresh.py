import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RefreshToken


def digest_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh(session: AsyncSession, owner: UUID, days: int) -> str:
    raw = secrets.token_urlsafe(48)
    session.add(RefreshToken(
        digest=digest_token(raw), family_id=uuid4(), user_id=owner,
        expires_at=datetime.now(UTC) + timedelta(days=days),
    ))
    await session.commit()
    return raw


async def _lock_family(session: AsyncSession, raw: str) -> RefreshToken | None:
    digest = digest_token(raw)
    family = await session.scalar(select(RefreshToken.family_id).where(
        RefreshToken.digest == digest
    ))
    if family is None:
        return None
    # Serialize all rotations and revocations in a family, including replay.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:family, 0))"),
        {"family": str(family)},
    )
    return await session.scalar(select(RefreshToken).where(
        RefreshToken.digest == digest
    ).execution_options(populate_existing=True))


async def rotate_refresh(session: AsyncSession, raw: str) -> tuple[UUID, str] | None:
    token = await _lock_family(session, raw)
    if token is None:
        await session.rollback()
        return None
    now = datetime.now(UTC)
    if token.used_at is not None or token.expires_at <= now:
        await session.execute(delete(RefreshToken).where(
            RefreshToken.family_id == token.family_id
        ))
        await session.commit()
        return None
    owner = token.user_id
    replacement = secrets.token_urlsafe(48)
    token.used_at = now
    session.add(RefreshToken(
        digest=digest_token(replacement), family_id=token.family_id,
        user_id=owner, expires_at=token.expires_at,
    ))
    await session.commit()
    return owner, replacement


async def revoke_refresh(session: AsyncSession, raw: str) -> None:
    token = await _lock_family(session, raw)
    if token is not None:
        await session.execute(delete(RefreshToken).where(
            RefreshToken.family_id == token.family_id
        ))
    await session.commit()
