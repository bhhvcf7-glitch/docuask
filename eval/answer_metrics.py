import re

from eval.metrics import percentile

MARKER = re.compile(r"\[([1-9][0-9]*)\]")


def assess(events: list[tuple[str, dict]], hits: list[dict], case: dict) -> dict:
    kinds = [kind for kind, _ in events]
    result = {"outcome": "error", "citation_valid": None, "gold_page_cited": None,
              "answer": "", "sources": [], "error": None}
    if kinds and kinds[-1] == "error":
        result["error"] = events[-1][1].get("message", "Unknown error")
        return result
    if kinds in (["refusal", "done"], ["generating", "refusal", "done"]):
        result["outcome"] = "refused"
        result["answer"] = events[-2][1]["answer"]
        return result
    if kinds != ["generating", "token", "citations", "done"]:
        result["error"] = "Unexpected event sequence"
        return result
    answer = events[1][1]["text"]
    sources = events[2][1]["sources"]
    numbers = [source["number"] for source in sources]
    cited = {int(number) for number in MARKER.findall(answer)}
    valid = bool(cited) and len(numbers) == len(set(numbers)) and cited == set(numbers)
    for source in sources:
        number = source["number"]
        if not isinstance(number, int) or not 1 <= number <= len(hits):
            valid = False
            continue
        hit = hits[number - 1]
        valid = valid and all(
            source.get(key) == expected for key, expected in {
                "chunk_id": str(hit["chunk_id"]),
                "document_id": str(hit["document_id"]),
                "filename": hit["filename"],
                "page_number": hit["page_number"],
                "text": hit["text"],
            }.items()
        )
    result.update(outcome="answered", answer=answer, sources=sources, citation_valid=valid)
    if case["answerable"]:
        result["gold_page_cited"] = valid and any(
            source["filename"] == case["expected_document"]
            and source["page_number"] == case["expected_page"] for source in sources
        )
    return result


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize_answers(rows: list[dict]) -> dict:
    positive = [row for row in rows if row["answerable"]]
    negative = [row for row in rows if not row["answerable"]]
    answered = [row for row in rows if row["outcome"] == "answered"]
    errors = sum(row["outcome"] == "error" for row in rows)
    latency = [row["total_ms"] for row in rows]
    return {
        "questions": len(rows),
        "answerable": len(positive),
        "unanswerable": len(negative),
        "answered": len(answered),
        "refused": sum(row["outcome"] == "refused" for row in rows),
        "errors": errors,
        "error_rate": ratio(errors, len(rows)),
        "answerable_refusal_rate": ratio(
            sum(row["outcome"] == "refused" for row in positive), len(positive)),
        "unanswerable_refusal_rate": ratio(
            sum(row["outcome"] == "refused" for row in negative), len(negative)),
        "unanswerable_answer_rate": ratio(
            sum(row["outcome"] == "answered" for row in negative), len(negative)),
        "citation_validity_among_answers": ratio(
            sum(row["citation_valid"] is True for row in answered), len(answered)),
        "gold_page_citation_rate_all_answerable": ratio(
            sum(row["outcome"] == "answered" and row["gold_page_cited"] is True for row in positive), len(positive)),
        "latency_ms_all_attempts": {
            "p50": percentile(latency, .5), "p95": percentile(latency, .95),
        } if latency else None,
    }
