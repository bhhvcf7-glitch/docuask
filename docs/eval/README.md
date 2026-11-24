# Evaluation results

| Metric | multilingual-e5-small, dense-only |
| --- | --- |
| hit@1 | Not measured |
| hit@3 | Not measured |
| hit@5 | Not measured |
| MRR@5 | Not measured |
| Unanswerable retrieval-gate refusal accuracy | Not measured |
| Answerable retrieval-gate recall | Not measured |
| Query latency p50 / p95 | Not measured |
| Search latency p50 / p95 | Not measured |
| Retrieval latency p50 / p95 | Not measured |

Run `python -m eval.run --output docs/eval/results.local.json` on a CPU with
embedding dependencies installed. Do not populate this table with deterministic
CI test results. The unanswerable score describes only the retrieval threshold,
not the LLM's ability to refuse an unsupported question.
