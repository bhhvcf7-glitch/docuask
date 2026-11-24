# Multilingual reranking and retrieval comparison

The optional CPU cross-encoder BAAI/bge-reranker-v2-m3 ranks only ready, owner-authorized chunks after dense or hybrid retrieval. It lazily loads using the existing embeddings extra, serializes model inference, batches eight pairs, and truncates model input at 512 tokens. Original cosine scores are retained for QA gating. A model failure returns search unavailable rather than silently producing a different ranking. Both features remain opt-in.

Set RETRIEVAL_MODE=hybrid, RERANK_ENABLED=true and optionally RERANK_CANDIDATES=20. Docker Compose forwards these settings. CPU model downloads and inference can be expensive.

Run on a dedicated migrated PostgreSQL and Qdrant instance with APP_ENV=test:
```bash
python -m eval.compare
python -m eval.compare --rerank --output docs/eval/rerank.local.json
```
The runner uses the production search path, temporary user and collection, the same bilingual corpus and questions, and reports page-level hit@1/3/5, MRR@5, retrieval gate proxies and end-to-end p50/p95 latency. It cleans up temporary records. The gate accepts any returned cosine score above the threshold, matching QA behavior. This is not answer correctness or calibrated confidence. The workflow publishes measured JSON artifacts; no performance improvement is asserted before results exist.
