import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.db.session import database_url

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok")


async def check_dependencies(settings: Settings) -> None:
    engine = create_async_engine(database_url(settings), pool_pre_ping=True)
    client = AsyncQdrantClient(url=settings.qdrant_url, timeout=4)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await client.get_collections()
    finally:
        await client.close()
        await engine.dispose()


@router.get("/ready", response_model=HealthStatus)
async def ready(settings: Settings = Depends(get_settings)) -> HealthStatus:
    try:
        await asyncio.wait_for(check_dependencies(settings), timeout=8)
    except (
        TimeoutError, OSError, SQLAlchemyError,
        ResponseHandlingException, UnexpectedResponse, ValueError,
    ) as exc:
        raise HTTPException(status_code=503, detail="Dependencies are not ready") from exc
    return HealthStatus(status="ok")
