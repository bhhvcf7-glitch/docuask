"""Evaluate production retrieval modes against a dedicated, migrated test database."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Chunk, Document, User
from app.db.session import database_url
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages
from app.retrieval.embeddings import E5Embeddings, MODEL_NAME
from app.retrieval.reranker import MODEL_NAME as RERANK_MODEL, load_model
from app.retrieval.vectors import VectorIndex
from app.services.search import search_documents
from eval.build_corpus import ROOT, build_corpus, load_manifest
from eval.metrics import summarize
from eval.run import check_corpus, load_questions


async def compare(pdf_dir: Path, *, include_reranker: bool) -> dict:
    settings = Settings()
    if settings.app_env != "test":
        raise ValueError("Set APP_ENV=test and use a dedicated evaluation database")
    manifest, questions = load_manifest(), load_questions()
    counts = check_corpus(pdf_dir, manifest, questions)
    owner = uuid4()
    engine = create_async_engine(database_url(settings))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = AsyncQdrantClient(url=settings.qdrant_url, timeout=30)
    embeddings = E5Embeddings()
    index = VectorIndex(client, f"eval_{owner.hex}", embeddings.dimension)
    reports = {}
    try:
        await index.ensure_collection()
        async with sessions.begin() as session:
            session.add(User(id=owner, email=f"{owner}@example.invalid", password_hash="disabled"))
            await session.flush()
            for doc in manifest["documents"]:
                document_id = uuid4()
                path = pdf_dir / doc["filename"]
                session.add(Document(
                    id=document_id, user_id=owner, original_name=doc["filename"],
                    storage_key=f"eval/{document_id}", media_type="application/pdf",
                    size_bytes=path.stat().st_size, sha256=uuid4().hex * 2, status="ready",
                ))
                await session.flush()
                pieces = chunk_pages(extract_pages(path))
                chunks = [
                    Chunk(id=uuid4(), user_id=owner, document_id=document_id,
                          ordinal=p.ordinal, page_number=p.page_number,
                          original_text=p.original_text, normalized_text=p.normalized_text)
                    for p in pieces
                ]
                session.add_all(chunks)
                await session.flush()
                vectors = await embeddings.documents([p.normalized_text for p in pieces])
                await index.upsert(
                    user_id=owner, document_id=document_id, chunks=chunks, vectors=vectors,
                )
        modes = [("dense", False), ("hybrid", False)]
        if include_reranker:
            load_model()
            modes.append(("hybrid", True))
        for mode, rerank in modes:
            configured = settings.model_copy(update={
                "retrieval_mode": mode, "rerank_enabled": rerank,
            })
            observations = []
            async with sessions() as session:
                await search_documents(
                    session, user_id=owner, question="warmup", limit=5,
                    settings=configured, embeddings=embeddings, index=index,
                )
                for case in questions:
                    started = perf_counter()
                    hits = await search_documents(
                        session, user_id=owner, question=case["question"], limit=5,
                        settings=configured, embeddings=embeddings, index=index,
                    )
                    elapsed = (perf_counter() - started) * 1000
                    observations.append({
                        "id": case["id"],
                        "hits": [{"document": h["filename"], "page": h["page_number"],
                                  "score": h["score"]} for h in hits],
                        "total_ms": elapsed,
                    })
            # Production path is timed end to end; component times are not measured.
            metric_rows = [dict(row, query_ms=0, search_ms=0) for row in observations]
            summary = summarize(questions, metric_rows, settings.qa_min_score)
            summary["latency_ms"] = {"total_ms": summary["latency_ms"]["total_ms"]}
            reports[mode + ("_reranked" if rerank else "")] = {
                "metrics": summary, "observations": observations,
            }
        return {"measured_at_utc": datetime.now(UTC).isoformat(), "counts": counts,
                "embedding_model": MODEL_NAME, "reranker_model": RERANK_MODEL if include_reranker else None,
                "threshold": settings.qa_min_score, "modes": reports}
    finally:
        try:
            async with sessions.begin() as session:
                await session.execute(delete(User).where(User.id == owner))
        finally:
            try:
                if await client.collection_exists(index.collection):
                    await client.delete_collection(index.collection)
            finally:
                await client.close()
                await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("docs/eval/compare.local.json"))
    args = parser.parse_args()
    pdf_dir = ROOT / "corpus" / "pdfs"
    build_corpus(pdf_dir)
    result = asyncio.run(compare(pdf_dir, include_reranker=args.rerank))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v["metrics"] for k, v in result["modes"].items()}, indent=2))


if __name__ == "__main__":
    main()
