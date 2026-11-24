from copy import deepcopy
from pathlib import Path

import pytest
from eval.build_corpus import build_corpus, load_manifest
from eval.metrics import percentile, summarize
from eval.run import check_corpus, load_questions


def test_generated_pdf_corpus_contains_verified_answers(tmp_path: Path) -> None:
    pdfs = build_corpus(tmp_path)
    assert len(pdfs) == 4
    assert all(path.read_bytes().startswith(b"%PDF-") for path in pdfs)
    questions = load_questions()
    counts = check_corpus(tmp_path, load_manifest(), questions)
    assert counts == {"documents": 4, "answerable": 40, "unanswerable": 8}
    assert len({question["id"] for question in questions}) == 48


def test_dataset_rejects_answer_on_wrong_source_page(tmp_path: Path) -> None:
    build_corpus(tmp_path)
    questions = deepcopy(load_questions())
    questions[0]["expected_page"] = 2
    with pytest.raises(ValueError, match="Answer is not in labeled PDF page"):
        check_corpus(tmp_path, load_manifest(), questions)


def test_dataset_rejects_unanswerable_with_leaked_answer_label(tmp_path: Path) -> None:
    build_corpus(tmp_path)
    questions = deepcopy(load_questions())
    questions[-1]["answer"] = "invented"
    with pytest.raises(ValueError, match="Unanswerable case has an answer label"):
        check_corpus(tmp_path, load_manifest(), questions)


def test_metrics_match_expected_page_not_just_filename() -> None:
    cases = [
        {"id": "a", "answerable": True, "expected_document": "a.pdf", "expected_page": 2},
        {"id": "b", "answerable": True, "expected_document": "b.pdf", "expected_page": 1},
        {"id": "c", "answerable": True, "expected_document": "a.pdf", "expected_page": 1},
        {"id": "d", "answerable": False},
        {"id": "e", "answerable": False},
    ]
    hits = [
        [{"document": "a.pdf", "page": 2, "score": 0.9}],
        [{"document": "b.pdf", "page": 2, "score": 0.8},
         {"document": "b.pdf", "page": 1, "score": 0.7}],
        [{"document": "a.pdf", "page": 2, "score": 0.6}],
        [{"document": "a.pdf", "page": 2, "score": 0.2}],
        [{"document": "a.pdf", "page": 2, "score": 0.9}],
    ]
    observations = [
        {"id": case["id"], "hits": matches, "query_ms": ms, "search_ms": 1.0,
         "total_ms": ms + 1}
        for case, matches, ms in zip(cases, hits, [10, 20, 30, 40, 50], strict=True)
    ]
    metrics = summarize(cases, observations, threshold=0.45)
    assert metrics["hit_at_1"] == 0.3333
    assert metrics["hit_at_3"] == metrics["hit_at_5"] == 0.6667
    assert metrics["mrr_at_5"] == 0.5
    assert metrics["retrieval_gate_answerable_recall"] == 1
    assert metrics["retrieval_gate_refusal_accuracy"] == 0.5
    assert metrics["latency_ms"]["query_ms"] == {"p50": 30, "p95": 48}


def test_metrics_refuse_empty_samples_and_bad_alignment() -> None:
    with pytest.raises(ValueError, match="Latency"):
        percentile([], 0.95)
    with pytest.raises(ValueError, match="observation"):
        summarize([{"id": "a"}], [], 0.45)


class FakeEmbeddings:
    dimension = 3

    async def documents(self, passages: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in passages]

    async def query(self, question: str) -> list[float]:
        return [1.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_evaluation_uses_existing_qdrant_index_without_model_weights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval import run

    build_corpus(tmp_path)
    monkeypatch.setattr(run, "E5Embeddings", FakeEmbeddings)
    report = await run.evaluate(
        tmp_path, load_manifest(), load_questions(), threshold=0.45
    )

    assert report["model"] == run.MODEL_NAME
    assert len(report["observations"]) == 48
    assert report["metrics"]["answerable_count"] == 40
    assert report["metrics"]["unanswerable_count"] == 8
    assert all(len(row["hits"]) <= 5 for row in report["observations"])
    assert all("total_ms" in row for row in report["observations"])
