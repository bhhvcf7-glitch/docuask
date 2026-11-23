# Architecture and boundaries

## Components

- **Frontend**: React + TypeScript + Vite + Tailwind, React Router, TanStack Query, react-pdf; `dir` on individual messages, logical CSS properties and a font covering Arabic and Latin glyphs. WebSocket is not required; answer delivery uses SSE via a cancellable fetch stream.
- **API**: FastAPI. Routers validate requests, depend on the authenticated principal, and delegate work to services. Services enforce authorization and domain invariants. Repositories scope every document/chat/chunk query by `user_id`.
- **PostgreSQL**: authoritative relational state and chat history. Every user-owned document and chat session includes `user_id`. Cascade policies are explicit. UUID keys; UTC timestamps.
- **Redis + ARQ**: ingestion queue, idempotency/retry bookkeeping, temporary answer cache, and rate limit counters. Jobs refer to document IDs, never trust a user ID supplied by the browser.
- **Document storage**: local filesystem via adapter in development. Object storage adapter is a later deployment concern. Never store large PDF binaries in PostgreSQL.
- **Qdrant**: payload includes `user_id`, `document_id`, `chunk_id`, and metadata; per-tenant filter is mandatory on both dense and sparse queries. PostgreSQL remains the source of truth for ownership.
- **Embedding worker**: loads multilingual-e5 once per worker process; configurable batch size; model version recorded with index metadata. Query-time embedding must use a separate preloaded runtime with bounded concurrency rather than loading the model per request.
- **Optional reranker**: cross-encoder reorders a bounded candidate set with measured latency.
- **LLM**: two provider implementations behind one narrow protocol; explicit network timeout/retry policy and circuit-breaker-style fallback. Stream emits answer events followed by authoritative citation/source metadata.

## Ingestion state machine

`queued -> processing -> ready` or `queued -> processing -> failed`, with retry transitions `failed -> queued` triggered by an explicit retry policy. Processing steps are `extract -> clean -> detect language -> chunk -> embed -> index -> commit ready status`.

Use a content hash to deduplicate within each account, not across accounts. Avoid persisting a `ready` state until indexed points have been checked. Job replays must upsert deterministic point IDs, and failed retries must not leave duplicated chunks. Delete or reindex must invalidate document-set-dependent cache keys.

## Text and citations

Persist **original display text**, **normalized search text**, the extraction method and its confidence/quality flags, and offsets relative to an identified representation. Keep a mapping from extracted text spans to PDF character boxes when possible. After OCR, derive box spans from OCR metadata; mark uncertain alignments as approximate, rather than promise a precise highlight.

Arabic normalization must be deterministic and versioned. Candidate steps: remove tatweel, optionally strip tashkeel for retrieval, normalize alef variants, normalize Arabic-Indic digits, and evaluate whether yaa / alif-maqsura / taa-marbuta folding helps or hurts. Mixed Arabic/Latin segments must preserve boundaries. Never replace source display text with normalized text. Reversal or reshaping repair of extracted Arabic PDF text needs evidence-based heuristics and tests; do not reverse every Arabic line.

For follow-up questions, rewrite to a standalone retrieval query while retaining original user wording and preserving citations from retrieved documents. Never use uncited chat history as evidence of source facts.

## Data trust boundaries

1. Validate extension, MIME, signature and detected content. Validate archive/container structure for DOCX, size and page limits, parsing budgets, and upload quotas. Use opaque storage names, never user-provided paths.
2. Use a signed JWT access token and rotating, stored-as-hash refresh tokens. Protect token storage and set revocation rules.
3. Authenticate at the API boundary; authorize documents/chats through ownership-scoped SQL. Apply a mandatory tenant filter when querying Qdrant. Never trust client-supplied `user_id`.
4. Retrieved documents are untrusted. Delimit passages and forbid instruction-following based on retrieved content; test malicious content. Defenses are probabilistic and cannot promise complete immunity.
5. The model proposes cited `chunk_id`s, but the API permits only IDs actually returned for that request. Citations with no verified retrieval link are rejected. Citation validation alone does not establish full answer faithfulness.
6. For SSE, stop generation on client abort where provider cancellation is supported; cap concurrent streams; define event IDs and retry semantics, avoiding duplicated persisted answers.

## Operations

- Structured JSON logging through structlog, request ID propagation and no secrets/text dumps by default.
- Prometheus counters/histograms for ingestion, retrieval, generation, errors and latency, with bounded label cardinality.
- Liveness checks process state; readiness checks required dependencies. Graceful shutdown stops acceptance of new jobs and drains/cancels in-flight work.
- CI will run lint, strict typing in core modules, unit/integration tests, coverage checks, build checks and a measured retrieval-quality gate.

## Scaling considerations

At 10x load, embedding CPU/GPU time, OCR throughput and LLM latency/cost likely dominate. Separate queue priorities, cache repeated embeddings, batch work and impose quotas. At 100x, partition or shard vectors and object storage, autoscale stateless API/worker pools, isolate tenant-heavy workloads and measure DB/Qdrant p95 before selecting infrastructure. These are hypotheses to benchmark, not measured bottlenecks.
