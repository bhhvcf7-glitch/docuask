import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.clients.llm import make_provider
from app.core.config import Settings
from app.db.models import Chunk, Document, User
from app.db.session import database_url
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages
from app.retrieval.embeddings import E5Embeddings, MODEL_NAME
from app.retrieval.vectors import VectorIndex
from app.services.qa import answer_events
from app.services.search import search_documents
from eval.answer_metrics import assess, summarize_answers
from eval.build_corpus import ROOT, build_corpus, load_manifest
from eval.run import DATASET, check_corpus, load_questions


async def evaluate_answers(pdf_dir: Path, settings: Settings, *, include_unanswerable: bool,
                           limit: int | None = None) -> dict:
    if settings.app_env != "test":
        raise ValueError("Set APP_ENV=test and use dedicated evaluation services")
    provider = make_provider(settings)
    manifest, questions = load_manifest(), load_questions()
    counts = check_corpus(pdf_dir, manifest, questions)
    cases = [q for q in questions if include_unanswerable or q["answerable"]]
    if limit is not None:
        cases = cases[:limit]
    owner = uuid4()
    engine = create_async_engine(database_url(settings))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = AsyncQdrantClient(url=settings.qdrant_url, timeout=30)
    embeddings = E5Embeddings()
    index = VectorIndex(client, f"eval_answers_{owner.hex}", embeddings.dimension)
    observations = []
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
                pieces = chunk_pages(extract_pages(
                    path, pdfium_fallback=settings.pdfium_fallback,
                    ocr_enabled=settings.ocr_enabled,
                ))
                chunks = [
                    Chunk(id=uuid4(), user_id=owner, document_id=document_id,
                          ordinal=p.ordinal, page_number=p.page_number,
                          original_text=p.original_text, normalized_text=p.normalized_text)
                    for p in pieces
                ]
                session.add_all(chunks)
                await session.flush()
                vectors = await embeddings.documents([p.normalized_text for p in pieces])
                await index.upsert(user_id=owner, document_id=document_id,
                                   chunks=chunks, vectors=vectors)
        await embeddings.query("warmup")
        for case in cases:
            eligible = []
            retrieved = []
            retrieval_ms = None
            progress_ms = None
            started = perf_counter()

            async def retrieve(session, **kwargs):
                nonlocal retrieval_ms
                before = perf_counter()
                hits = await search_documents(session, **kwargs, embeddings=embeddings, index=index)
                retrieval_ms = (perf_counter() - before) * 1000
                retrieved.extend(hits)
                eligible.extend(h for h in hits if h["score"] >= settings.qa_min_score)
                return hits

            async with sessions() as session:
                events = []
                async for item in answer_events(
                    session, user_id=owner, question=case["question"], limit=5,
                    settings=settings, provider=provider, search=retrieve,
                ):
                    lines = item.splitlines()
                    kind = lines[0][7:]
                    events.append((kind, json.loads(lines[1][6:])))
                    if kind == "generating":
                        progress_ms = (perf_counter() - started) * 1000
            result = assess(events, eligible, case)
            observations.append({
                "id": case["id"], "language": case["language"],
                "answerable": case["answerable"], "question": case["question"],
                "reference_answer": case["answer"],
                "expected_document": case["expected_document"],
                "expected_page": case["expected_page"],
                "retrieved": [{"document": h["filename"], "page": h["page_number"],
                               "score": h["score"]} for h in retrieved],
                "events": [kind for kind, _ in events],
                "retrieval_ms": retrieval_ms, "progress_ms": progress_ms,
                "total_ms": (perf_counter() - started) * 1000, **result,
            })
            print(f"{len(observations)}/{len(cases)} {case['id']}: {result['outcome']}", flush=True)
        return {
            "schema_version": 1, "measured_at_utc": datetime.now(UTC).isoformat(),
            "corpus_type": manifest["kind"], "counts": counts,
            "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            "provider": settings.llm_provider, "model": settings.llm_model,
            "embedding_model": MODEL_NAME, "retrieval_mode": settings.retrieval_mode,
            "rerank_enabled": settings.rerank_enabled, "rerank_candidates": settings.rerank_candidates,
            "threshold": settings.qa_min_score,
            "generation_timeout_seconds": settings.qa_generation_timeout_seconds,
            "answer_char_limit": settings.qa_max_answer_chars,
            "limit": 5, "scope": "QA service; excludes HTTP, rewrite and conversation persistence",
            "metrics": summarize_answers(observations),
            "by_language": {lang: summarize_answers(
                [row for row in observations if row["language"] == lang]
            ) for lang in ("ar", "en")},
            "observations": observations,
        }
    finally:
        try:
            async with sessions.begin() as session:
                await session.execute(delete(User).where(User.id == owner))
        finally:
            try:
                if await client.collection_exists(index.collection):
                    await client.delete_collection(index.collection)
            finally:
                try:
                    await client.close()
                finally:
                    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure answer-level structural behavior")
    parser.add_argument("--run", action="store_true", help="Explicitly authorize model inference")
    parser.add_argument("--include-unanswerable", action="store_true")
    parser.add_argument("--allow-remote", action="store_true", help="Allow remote provider costs")
    parser.add_argument("--limit", type=int, help="Small smoke subset, not a benchmark")
    parser.add_argument("--output", type=Path, default=Path("docs/eval/answers.local.json"))
    args = parser.parse_args()
    if not args.run:
        parser.error("--run is required to authorize model inference")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    settings = Settings()
    if settings.app_env != "test":
        parser.error("APP_ENV=test and dedicated evaluation services are required")
    if settings.llm_provider == "openai" and not args.allow_remote:
        parser.error("--allow-remote is required for OpenAI-compatible inference")
    from urllib.parse import urlsplit

    if settings.llm_provider == "ollama" and not args.allow_remote:
        if urlsplit(settings.ollama_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error("--allow-remote is required for non-loopback Ollama")
    pdf_dir = ROOT / "corpus" / "pdfs"
    build_corpus(pdf_dir)
    report = asyncio.run(evaluate_answers(
        pdf_dir, settings, include_unanswerable=args.include_unanswerable, limit=args.limit,
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
