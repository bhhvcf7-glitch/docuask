from eval.answer_metrics import assess, summarize_answers

HIT = {"chunk_id": "c", "document_id": "d", "filename": "doc.pdf",
       "page_number": 2, "text": "Evidence", "score": .9}
CASE = {"answerable": True, "expected_document": "doc.pdf", "expected_page": 2}
SOURCE = {"number": 1, **{k: v for k, v in HIT.items() if k != "score"}}


def test_valid_answer_and_gold_page():
    result = assess([("generating", {}), ("token", {"text": "Fact [1]"}),
                     ("citations", {"sources": [SOURCE]}), ("done", {})], [HIT], CASE)
    assert result["outcome"] == "answered"
    assert result["citation_valid"] is True
    assert result["gold_page_cited"] is True


def test_invented_mapping():
    result = assess([("generating", {}), ("token", {"text": "Fact [1]"}),
                     ("citations", {"sources": [dict(SOURCE, chunk_id="wrong")]}),
                     ("done", {})], [HIT], CASE)
    assert result["citation_valid"] is False
    assert result["gold_page_cited"] is False


def test_wrong_page_is_not_invalid_citation():
    result = assess([("generating", {}), ("token", {"text": "Fact [1]"}),
                     ("citations", {"sources": [SOURCE]}), ("done", {})],
                    [HIT], dict(CASE, expected_page=3))
    assert result["citation_valid"] is True
    assert result["gold_page_cited"] is False


def test_error_is_not_refusal():
    result = assess([("generating", {}), ("error", {"message": "timeout"})], [], CASE)
    assert result["outcome"] == "error"
    assert result["citation_valid"] is None
    assert assess([("generating", {})], [], CASE)["outcome"] == "error"


def test_refusal():
    assert assess([("refusal", {"answer": "No evidence"}), ("done", {})],
                  [], CASE)["outcome"] == "refused"


def test_metrics_denominators():
    rows = [
        {"answerable": True, "outcome": "answered", "citation_valid": True,
         "gold_page_cited": True, "total_ms": 10},
        {"answerable": True, "outcome": "error", "total_ms": 20},
        {"answerable": False, "outcome": "refused", "total_ms": 30},
        {"answerable": False, "outcome": "answered", "citation_valid": False,
         "gold_page_cited": None, "total_ms": 40},
    ]
    summary = summarize_answers(rows)
    assert summary["gold_page_citation_rate_all_answerable"] == .5
    assert summary["citation_validity_among_answers"] == .5
    assert summary["unanswerable_refusal_rate"] == .5
    assert summary["error_rate"] == .25
    assert summary["answerable_refusal_rate"] == 0
    assert summarize_answers([])["citation_validity_among_answers"] is None
