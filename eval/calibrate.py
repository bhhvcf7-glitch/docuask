import argparse
import json
import math
from pathlib import Path

from eval.metrics import percentile

DATASET = Path(__file__).resolve().parent / "dataset" / "questions.jsonl"


def collect_scores(cases, observations, method):
    labels = {case["id"]: case["answerable"] for case in cases}
    hits = {row["id"]: row["hits"] for row in observations}
    if len(labels) != len(cases) or len(hits) != len(observations):
        raise ValueError("Duplicate IDs")
    if labels.keys() != hits.keys():
        raise ValueError("Question and observation IDs differ")
    if method not in {"top1", "max", "margin"}:
        raise ValueError("Unknown score method")
    positive, negative = [], []
    for key, label in labels.items():
        if not isinstance(label, bool):
            raise ValueError("Invalid answerable label")
        scores = [float(hit["score"]) for hit in hits[key][:5]]
        if any(not math.isfinite(s) or not -1 <= s <= 1 for s in scores):
            raise ValueError("Invalid cosine score")
        value = None
        if scores:
            if method == "top1":
                value = scores[0]
            elif method == "max":
                value = max(scores)
            elif len(scores) >= 2:
                ordered = sorted(scores, reverse=True)
                value = ordered[0] - ordered[1]
        (positive if label else negative).append(value)
    if not positive or not negative:
        raise ValueError("Both question classes are required")
    return positive, negative


def describe(scores: list[float | None]) -> dict:
    values = [s for s in scores if s is not None]
    result = {"count": len(scores), "missing": len(scores) - len(values)}
    if values:
        result.update(min=min(values), q1=percentile(values, .25),
                      median=percentile(values, .5), q3=percentile(values, .75),
                      max=max(values))
    return result


def gate_metrics(positive, negative, threshold: float) -> dict:
    recall = sum(s is not None and s >= threshold for s in positive) / len(positive)
    refusal = sum(s is None or s < threshold for s in negative) / len(negative)
    return {"threshold": threshold, "recall": recall, "refusal": refusal,
            "balanced_accuracy": (recall + refusal) / 2}


def sweep(positive, negative, lower=-1.0, upper=1.0, baseline=None) -> list[dict]:
    values = sorted({s for s in positive + negative if s is not None})
    thresholds = {lower, upper, *values}
    thresholds.update(a + (b - a) / 2 for a, b in zip(values, values[1:], strict=False))
    if values and values[-1] < upper:
        thresholds.add(values[-1] + (upper - values[-1]) / 2)
    if baseline is not None:
        thresholds.add(baseline)
    return [gate_metrics(positive, negative, t) for t in sorted(thresholds)]


def select_candidate(rows: list[dict], min_recall: float) -> dict | None:
    eligible = [row for row in rows if row["recall"] >= min_recall]
    return max(eligible, key=lambda r: (r["refusal"], r["recall"], -r["threshold"]),
               default=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze retrieval gate calibration")
    parser.add_argument("results", type=Path)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--mode", default="dense")
    parser.add_argument("--margin", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.results.read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if "modes" in report:
        if args.mode not in report["modes"]:
            parser.error("Unknown retrieval mode")
        observations = report["modes"][args.mode]["observations"]
        baseline = float(report["threshold"])
    else:
        if args.mode != "dense":
            parser.error("Expected dense-only report")
        observations = report["observations"]
        baseline = float(report["qa_min_score_used"])
    for method in ["top1", "max"] + (["margin"] if args.margin else []):
        positive, negative = collect_scores(cases, observations, method)
        print(method, json.dumps({"answerable": describe(positive),
                                  "unanswerable": describe(negative)}, indent=2))
        margin = method == "margin"
        rows = sweep(positive, negative, 0 if margin else -1, 2 if margin else 1,
                     None if margin else baseline)
        print("Threshold             Recall    Refusal")
        for row in rows:
            print(f"{row['threshold']:20.16f} {row['recall']:8.2%} {row['refusal']:8.2%}")
        for minimum in (1., .95, .9, .8):
            print(f"Minimum recall {minimum:.0%}: {select_candidate(rows, minimum)}")
    print("Candidates are fitted to this corpus, not independently validated.")


if __name__ == "__main__":
    main()
