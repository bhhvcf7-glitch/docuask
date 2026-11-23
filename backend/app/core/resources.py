from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.retrieval.embeddings import E5Embeddings
from app.retrieval.vectors import VectorIndex


@dataclass
class AppResources:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    qdrant: AsyncQdrantClient
    embeddings: E5Embeddings
    index: VectorIndex
