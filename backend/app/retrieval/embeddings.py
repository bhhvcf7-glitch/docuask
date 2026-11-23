from functools import lru_cache

from starlette.concurrency import run_in_threadpool

from app.ingestion.text import normalize_arabic

MODEL_NAME = "intfloat/multilingual-e5-small"
VECTOR_SIZE = 384


@lru_cache(maxsize=1)
def load_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME, device="cpu")


class E5Embeddings:
    dimension = VECTOR_SIZE

    async def documents(self, passages: list[str]) -> list[list[float]]:
        if not passages:
            return []
        texts = [f"passage: {text}" for text in passages]
        return await run_in_threadpool(self._encode, texts)

    async def query(self, question: str) -> list[float]:
        vectors = await run_in_threadpool(
            self._encode, [f"query: {normalize_arabic(question)}"]
        )
        return vectors[0]

    @staticmethod
    def _encode(texts: list[str]) -> list[list[float]]:
        model = load_model()
        vectors = model.encode(
            texts, normalize_embeddings=True, batch_size=16, show_progress_bar=False
        )
        return vectors.tolist()
