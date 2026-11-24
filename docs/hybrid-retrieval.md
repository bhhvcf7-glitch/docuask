# Hybrid retrieval

Opt in with RETRIEVAL_MODE=hybrid after `alembic upgrade head`. Existing normalized chunk text is indexed in PostgreSQL using a GIN expression index and the simple text search configuration. No Qdrant reindex is required.

The query uses normalized Arabic and case-insensitive lexical terms, OR matching, and ts_rank_cd. This is lexical full-text retrieval, not BM25 or Arabic morphological stemming. Up to four times the requested limit (maximum 100) is retrieved per branch. Reciprocal rank fusion uses k=60, deterministic UUID tie breaks, and deduplicates chunk IDs. Lexical-only candidates are rescored against their existing Qdrant vectors; missing vectors are omitted. The public score remains cosine similarity so the QA threshold is not applied to RRF scores. The database remains the final ownership and ready-status authority. Dense mode is unchanged and remains the default based on historical measured quality and latency.

CI exercises both modes with real PostgreSQL and Qdrant. Run `python -m pytest backend/tests/test_hybrid.py backend/tests/test_search_integration.py -q` with RUN_DB_TESTS=1 and RUN_VECTOR_TESTS=1 for integration coverage. The production-path comparison measures dense and hybrid; see [results](eval/production-results.md). Hybrid remains opt-in.
