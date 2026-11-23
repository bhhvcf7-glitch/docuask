from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    page_number: int
    text: str
    score: float
