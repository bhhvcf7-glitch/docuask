# Multilingual reranking and retrieval comparison

The optional CPU cross-encoder BAAI/bge-reranker-v2-m3 ranks only ready, owner-authorized chunks after dense or hybrid retrieval. It lazily loads using the existing embeddings extra, serializes model inference, batches eight pairs, and truncates model input at 512 tokens. Original cosine scores are retained for QA gating. A model failure returns search unavailable rather than silently producing a different ranking. Both features remain opt-in.

Set RETRIEVAL_MODE=hybrid, RERANK_ENABLED=true and optionally RERANK_CANDIDATES=20. Docker Compose forwards these settings. CPU model downloads and inference can be expensive.

Run on a dedicated migrated PostgreSQL and Qdrant instance with APP_ENV=test:
```bash
python -m eval.compare
python -m eval.compare --rerank --output docs/eval/rerank.local.json
```
The runner uses the production search path, temporary user and collection, the same bilingual corpus and questions, and reports page-level hit@1/3/5, MRR@5, retrieval gate proxies and end-to-end p50/p95 latency. It cleans up temporary records. The gate accepts any returned cosine score at or above the threshold, matching QA behavior. This is not answer correctness or calibrated confidence. The workflow publishes measured JSON artifacts; Historical measured results are in docs/eval/production-results.md.


## Candidate-count experiment

On dedicated migrated test services, install the embeddings extra and run:

```bash
python -m eval.compare --rerank --candidates 5 8 12 20 --output docs/eval/rerank-sweep.local.json
```

This compares dense, hybrid, and four hybrid reranking candidate budgets in the same run, with five final hits and the existing cosine threshold. Each mode has one warm-up query. For explicit budgets the mode keys are hybrid_reranked_5, hybrid_reranked_8, hybrid_reranked_12 and hybrid_reranked_20. Without the new flag the original mode key is preserved.

Candidate count affects both the cross-encoder input size and the upstream hybrid search depth, so this is a system-level comparison, not an isolated cross-encoder timing study. Record CPU model, thread settings, package and model revisions, and repeat with varied mode order before interpreting small latency differences. The report includes dataset hash and candidate count. Use paired question IDs to inspect rank changes and report Arabic and English results separately. No new measured gains are claimed.

Dense stays the default: historical reranking improved first-page ranking but incurred substantial CPU latency and did not improve refusal accuracy. Evaluate smaller candidate budgets before considering adaptive routing; do not substitute reranker logits for the cosine gate without independent calibration.
