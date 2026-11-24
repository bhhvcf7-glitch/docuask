import math


def percentile(samples: list[float], proportion: float) -> float:
    if not samples:
        raise ValueError("Latency samples cannot be empty")
    if not 0 <= proportion <= 1:
        raise ValueError("Invalid percentile")
    ordered = sorted(samples)
    rank = (len(ordered) - 1) * proportion
    lower = math.floor(rank)
    upper = math.ceil(rank)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def summarize(cases: list[dict], observations: list[dict], threshold: float) -> dict:
    if not -1 <= threshold <= 1:
        raise ValueError("Cosine threshold must be between -1 and 1")
    if len(cases) != len(observations):
        raise ValueError("Each question must have one observation")

    observed = {item["id"]: item for item in observations}
    if len(observed) != len(cases):
        raise ValueError("Observation IDs must be unique")
    if set(observed) != {item["id"] for item in cases}:
        raise ValueError("Question and observation IDs differ")

    answerable = [item for item in cases if item["answerable"]]
    unanswered = [item for item in cases if not item["answerable"]]
    if not answerable or not unanswered:
        raise ValueError("Both answerable and unanswerable cases are required")

    ranks: list[int | None] = []
    correct_gate = 0
    refused = 0
    for question in cases:
        matches = observed[question["id"]]["hits"][:5]
        is_supported = bool(matches) and matches[0]["score"] >= threshold
        if question["answerable"]:
            if is_supported:
                correct_gate += 1
            rank = next(
                (
                    index for index, match in enumerate(matches, start=1)
                    if match["document"] == question["expected_document"]
                    and match["page"] == question["expected_page"]
                ),
                None,
            )
            ranks.append(rank)
        elif not is_supported:
            refused += 1

    count = len(answerable)
    latency = {}
    for key in ("query_ms", "search_ms", "total_ms"):
        samples = [float(item[key]) for item in observations]
        latency[key] = {
            "p50": round(percentile(samples, 0.50), 3),
            "p95": round(percentile(samples, 0.95), 3),
        }

    return {
        "answerable_count": count,
        "unanswerable_count": len(unanswered),
        "hit_at_1": round(sum(rank is not None and rank <= 1 for rank in ranks) / count, 4),
        "hit_at_3": round(sum(rank is not None and rank <= 3 for rank in ranks) / count, 4),
        "hit_at_5": round(sum(rank is not None and rank <= 5 for rank in ranks) / count, 4),
        "mrr_at_5": round(sum(1 / rank for rank in ranks if rank is not None) / count, 4),
        "retrieval_gate_answerable_recall": round(correct_gate / count, 4),
        "retrieval_gate_refusal_accuracy": round(refused / len(unanswered), 4),
        "latency_ms": latency,
    }
