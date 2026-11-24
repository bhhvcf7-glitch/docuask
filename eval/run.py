import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID, uuid5

from qdrant_client import AsyncQdrantClient

from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages
from app.ingestion.text import normalize_arabic
from app.retrieval.embeddings import E5Embeddings, MODEL_NAME
from app.retrieval.vectors import VectorIndex
from eval.build_corpus import ROOT, build_corpus, load_manifest
from eval.metrics import summarize

NAMESPACE = UUID("40f284a7-1658-4846-9d94-a1e0f9193d2d")
DATASET = ROOT / "dataset" / "questions.jsonl"
RESULTS = ROOT.parent / "docs" / "eval" / "results.local.json"


def load_questions() -> list[dict]:
    return [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def check_corpus(pdf_dir: Path, manifest: dict, questions: list[dict]) -> dict:
    documents = manifest["documents"]
    if len(documents) < 4 or len(documents) > 8:
        raise ValueError("Expected four to eight PDFs")
    if len({doc["id"] for doc in documents}) != len(documents):
        raise ValueError("Duplicate corpus document IDs")
    total_pages = sum(len(doc["pages"]) for doc in documents)
    if not 30 <= total_pages <= 50:
        raise ValueError("Expected 30 to 50 pages")
    if len({doc["filename"] for doc in documents}) != len(documents):
        raise ValueError("Duplicate corpus filenames")
    if {doc["language"] for doc in documents} != {"ar", "en"}:
        raise ValueError("The corpus must include Arabic and English")
    if len({case["id"] for case in questions}) != len(questions):
        raise ValueError("Duplicate evaluation question IDs")
    if len({case["question"] for case in questions}) != len(questions):
        raise ValueError("Duplicate evaluation questions")

    pages_by_file = {}
    chunk_total = 0
    for doc in documents:
        pages = dict(extract_pages(pdf_dir / doc["filename"]))
        expected = {page["number"] for page in doc["pages"]}
        if set(pages) != expected:
            raise ValueError(f"Missing or unexpected extracted pages: {doc['filename']}")
        for page in doc["pages"]:
            extracted = normalize_arabic(pages[page["number"]])
            if not all(normalize_arabic(line) in extracted for line in page["lines"]):
                raise ValueError(
                    f"PDF extraction differs from reference text: {doc['filename']}, "
                    f"page {page['number']}"
                )
        for number, text in pages.items():
            pieces = chunk_pages([(number, text)])
            if len(pieces) < 2:
                raise ValueError(
                    f"Evaluation page has fewer than two chunks: "
                    f"{doc['filename']}, page {number}"
                )
            chunk_total += len(pieces)
        pages_by_file[doc["filename"]] = pages

    answerable_count = 0
    negative_count = 0
    for case in questions:
        if not case["question"].strip() or case["language"] not in {"ar", "en"}:
            raise ValueError(f"Invalid question: {case['id']}")
        if case["answerable"]:
            answerable_count += 1
            pages = pages_by_file.get(case["expected_document"])
            if pages is None or case["expected_page"] not in pages:
                raise ValueError(f"Invalid document/page label: {case['id']}")
            if not case["answer"] or normalize_arabic(case["answer"]) not in normalize_arabic(
                pages[case["expected_page"]]
            ):
                raise ValueError(f"Answer is not in labeled PDF page: {case['id']}")
        else:
            negative_count += 1
            if any(case.get(field) is not None for field in (
                "answer", "expected_document", "expected_page"
            )):
                raise ValueError(f"Unanswerable case has an answer label: {case['id']}")
    if answerable_count < 60 or negative_count < 10:
        raise ValueError("Expected at least 60 answerable and 10 unanswerable questions")
    return {
        "documents": len(documents), "pages": total_pages, "chunks": chunk_total,
        "answerable": answerable_count, "unanswerable": negative_count,
    }


async def evaluate(pdf_dir: Path, manifest: dict, questions: list[dict], threshold: float) -> dict:
    embeddings = E5Embeddings()
    owner = uuid5(NAMESPACE, "eval-user")
    client = AsyncQdrantClient(":memory:")
    index = VectorIndex(client, "docuask_evaluation", embeddings.dimension)
    chunk_locations = {}
    chunks_per_document = {}
    try:
        await index.ensure_collection()
        indexed_at = perf_counter()
        for doc in manifest["documents"]:
            document_id = uuid5(NAMESPACE, doc["id"])
            pieces = chunk_pages(extract_pages(pdf_dir / doc["filename"]))
            chunks_per_document[doc["filename"]] = len(pieces)
            chunks = []
            for piece in pieces:
                chunk_id = uuid5(NAMESPACE, f"{doc['id']}:{piece.ordinal}")
                chunks.append(SimpleNamespace(
                    id=chunk_id, ordinal=piece.ordinal, page_number=piece.page_number,
                ))
                chunk_locations[chunk_id] = (doc["filename"], piece.page_number)
            vectors = await embeddings.documents([piece.normalized_text for piece in pieces])
            await index.upsert(
                user_id=owner, document_id=document_id, chunks=chunks, vectors=vectors,
            )
        indexing_ms = (perf_counter() - indexed_at) * 1000

        # Warm model and retrieval before measuring question latency.
        await embeddings.query("warmup")
        observations = []
        for case in questions:
            started = perf_counter()
            vector = await embeddings.query(case["question"])
            encoded = perf_counter()
            matches = await index.search(user_id=owner, vector=vector, limit=5)
            searched = perf_counter()
            hits = [
                {"document": chunk_locations[match.chunk_id][0],
                 "page": chunk_locations[match.chunk_id][1],
                 "score": round(match.score, 6)}
                for match in matches
            ]
            observations.append({
                "id": case["id"], "hits": hits,
                "query_ms": round((encoded - started) * 1000, 3),
                "search_ms": round((searched - encoded) * 1000, 3),
                "total_ms": round((searched - started) * 1000, 3),
            })
        return {
            "schema_version": 1,
            "measured_at_utc": datetime.now(UTC).isoformat(),
            "model": MODEL_NAME,
            "retrieval": "dense_cosine_in_memory_qdrant",
            "qa_min_score_used": threshold,
            "corpus_type": manifest["kind"],
            "indexed_chunk_count": len(chunk_locations),
            "indexed_document_count": len(manifest["documents"]),
            "indexed_page_count": sum(len(doc["pages"]) for doc in manifest["documents"]),
            "chunks_per_document": chunks_per_document,
            "indexing_ms": round(indexing_ms, 3),
            "metrics": summarize(questions, observations, threshold),
            "observations": observations,
        }
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate DocuAsk dense retrieval on CPU")
    parser.add_argument("--check", action="store_true", help="Validate PDFs and labels; no model")
    parser.add_argument("--output", type=Path, default=RESULTS)
    parser.add_argument("--font", type=Path, help="Local Arabic TrueType font for PDF generation")
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    pdf_dir = ROOT / "corpus" / "pdfs"
    build_corpus(pdf_dir, font_path=args.font)
    manifest, questions = load_manifest(), load_questions()
    counts = check_corpus(pdf_dir, manifest, questions)
    print(
        f"Corpus validated: {counts['documents']} PDFs, {counts['pages']} pages, "
        f"{counts['chunks']} chunks, {counts['answerable']} answerable, "
        f"{counts['unanswerable']} unanswerable"
    )
    if args.check:
        return

    from app.core.config import Settings

    threshold = args.threshold
    if threshold is None:
        threshold = Settings().qa_min_score
    report = asyncio.run(evaluate(pdf_dir, manifest, questions, threshold))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Indexed {report['indexed_chunk_count']} chunks across "
          f"{report['indexed_page_count']} pages")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Saved measured results to {args.output}")


if __name__ == "__main__":
    main()
