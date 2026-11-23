from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_name: str
    size_bytes: int
    sha256: str
    status: Literal["queued", "processing", "ready", "failed"]
    created_at: datetime
