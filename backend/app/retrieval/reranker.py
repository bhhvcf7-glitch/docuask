import math
from functools import lru_cache
from threading import Lock

from starlette.concurrency import run_in_threadpool

MODEL_NAME = "BAAI/bge-reranker-v2-m3"
_model_lock = Lock()


@lru_cache(maxsize=1)
def load_model():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(MODEL_NAME, device="cpu", max_length=512, trust_remote_code=False)


def reorder(hits: list[dict], scores: list[float]) -> list[dict]:
    if len(hits) != len(scores) or not all(math.isfinite(score) for score in scores):
        raise ValueError("Invalid reranker scores")
    return [
        hit for hit, _ in sorted(
            zip(hits, scores, strict=True), key=lambda pair: -pair[1]
        )
    ]


def _predict(question: str, hits: list[dict]) -> list[dict]:
    with _model_lock:
        scores = load_model().predict(
            [(question, hit["text"]) for hit in hits],
            batch_size=8, show_progress_bar=False,
        )
    return reorder(hits, [float(score) for score in scores])


async def rerank(question: str, hits: list[dict]) -> list[dict]:
    if len(hits) < 2:
        return hits
    return await run_in_threadpool(_predict, question, hits)
