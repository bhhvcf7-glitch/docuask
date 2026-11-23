import asyncio
from typing import Annotated, Literal

from app.core.resources import AppResources
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_resources

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok")


async def check_dependencies(resources: AppResources) -> None:
    async with resources.engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    await resources.qdrant.get_collections()


@router.get("/ready", response_model=HealthStatus)
async def ready(
    resources: Annotated[AppResources, Depends(get_resources)],
) -> HealthStatus:
    try:
        await asyncio.wait_for(check_dependencies(resources), timeout=8)
    except (
        TimeoutError, OSError, SQLAlchemyError,
        ResponseHandlingException, UnexpectedResponse, ValueError,
    ) as exc:
        raise HTTPException(status_code=503, detail="Dependencies are not ready") from exc
    return HealthStatus(status="ok")
