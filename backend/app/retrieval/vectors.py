from dataclasses import dataclass
from uuid import UUID, uuid5

from qdrant_client import AsyncQdrantClient, models

POINT_NAMESPACE = UUID("38f9922d-a43c-4f65-b10a-11381ac35387")


@dataclass(frozen=True)
class Match:
    chunk_id: UUID
    score: float


def point_id(document_id: UUID, ordinal: int) -> str:
    return str(uuid5(POINT_NAMESPACE, f"{document_id}:{ordinal}"))


class VectorIndex:
    def __init__(self, client: AsyncQdrantClient, collection: str, dimension: int):
        self.client = client
        self.collection = collection
        self.dimension = dimension

    async def ensure_collection(self) -> None:
        if await self.client.collection_exists(self.collection):
            details = await self.client.get_collection(self.collection)
            vectors = details.config.params.vectors
            if not isinstance(vectors, models.VectorParams) or vectors.size != self.dimension:
                raise ValueError("Vector collection dimension does not match configured model")
            return
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=self.dimension, distance=models.Distance.COSINE
            ),
        )
        await self.client.create_payload_index(
            collection_name=self.collection,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    async def upsert(
        self, *, user_id: UUID, document_id: UUID, chunks: list, vectors: list[list[float]]
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Each chunk requires one vector")
        if not chunks:
            return
        points = [
            models.PointStruct(
                id=point_id(document_id, chunk.ordinal),
                vector=vector,
                payload={
                    "user_id": str(user_id),
                    "document_id": str(document_id),
                    "chunk_id": str(chunk.id),
                    "page_number": chunk.page_number,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self.client.upsert(
            collection_name=self.collection, points=points, wait=True
        )

    async def search(
        self, *, user_id: UUID, vector: list[float], limit: int = 5
    ) -> list[Match]:
        if len(vector) != self.dimension:
            raise ValueError("Query vector dimension mismatch")
        found = await self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=models.Filter(must=[
                models.FieldCondition(
                    key="user_id", match=models.MatchValue(value=str(user_id))
                )
            ]),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [
            Match(chunk_id=UUID(str(hit.payload["chunk_id"])), score=hit.score)
            for hit in found.points
        ]
