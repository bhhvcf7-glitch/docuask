# Delivery plan

This is an ordered plan, not a record of completed work. Each implementation phase will have exact file paths, runnable commands, verification criteria, one conventional commit, and two or three design-review questions. Complexity bands indicate relative effort only; they are not delivery-time promises.

| Phase | Scope | Relative effort | Done when |
| --- | --- | --- | --- |
| 0 | Repository layout, architecture, schema, delivery plan | Small | Design artifacts reviewed |
| 1 | Repository scaffolding, Docker Compose, Makefile, CI skeleton | Medium | `make dev` starts health endpoints and services |
| 2 | Pydantic settings, request IDs, structlog, health/readiness | Small | Config validation and structured logs tested |
| 3 | Async PostgreSQL models and Alembic migrations | Medium | Upgrade/downgrade and ownership constraints tested |
| 4 | Password registration/login and rotating JWT refresh tokens | Large | Cross-user isolation and token lifecycle tests pass |
| 5 | File upload, content sniffing, hash deduplication, storage | Medium | Malformed and oversize files fail safely |
| 6 | PDF/DOCX/TXT/MD parsing and selective OCR | Large | Image-only Arabic PDF and corruption fixtures handled |
| 7 | Arabic normalization, bidirectional-text repair heuristics | Large | Targeted unit tests document transformations and exceptions |
| 8 | Structure-aware chunking and span metadata | Medium | Page/section/offset tests pass |
| 9 | Embedding runtime and Qdrant index versioning | Large | Repeated indexing is idempotent |
| 10 | Redis/ARQ ingestion pipeline, retries and progress | Large | Worker retry and full fixture ingestion pass |
| 11 | Dense/sparse retrieval with RRF and metadata filters | Large | Retrieval unit and integration tests pass |
| 12 | Optional multilingual reranking | Medium | Reranking toggle and latency measured |
| 13 | OpenAI-compatible and Ollama provider implementations | Medium | Both satisfy same provider contract |
| 14 | Grounded QA, relevance refusal, citation validation, SSE | Large | Invalid citations rejected; streaming/cancellation tested |
| 15 | Chat history and standalone-query rewriting | Medium | Follow-ups retrieve correctly; chats are isolated |
| 16 | Cache invalidation, throttling, timeout/retry safeguards | Medium | Abuse and stale-cache tests pass |
| 17 | Metrics, operational errors, tracing hooks, hardening | Medium | Dashboards or metrics and failure-mode checks available |
| 18 | Frontend foundation, auth, accessibility and directionality | Medium | RTL/LTR interactions verified |
| 19 | Upload UI and ingest status | Medium | Queued/processing/failed/ready flows usable |
| 20 | Chat UI, sources, abortable SSE | Large | Typed messages and cancellation work |
| 21 | PDF viewer with citation navigation and highlights | Large | Geometry-backed highlights confirmed on fixtures |
| 22 | Bilingual public-corpus evaluation set (>=40 pairs) | Large | Dataset independently reviewed, includes unanswerable items |
| 23 | Reproducible evaluation across retrieval modes | Large | Real hit@k/MRR/latency, refusal metrics and judge limitations saved |
| 24 | CI retrieval regression gate and deployment | Large | Threshold gate, builds and configured deployments verified |
| 25 | Documentation, ADRs, security, scaling, interview Q&A | Medium | All deliverables accurate to actual functionality and evidence |

## Proposed repository structure

```text
docuask/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── retrieval-eval.yml
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── documents.py
│   │   │       ├── chats.py
│   │   │       └── health.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   ├── models/
│   │   │   ├── session.py
│   │   │   └── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── ingestion.py
│   │   │   ├── retrieval.py
│   │   │   ├── qa.py
│   │   │   └── citations.py
│   │   ├── ingestion/
│   │   │   ├── parsing/
│   │   │   ├── normalization.py
│   │   │   ├── chunking.py
│   │   │   └── tasks.py
│   │   ├── retrieval/
│   │   │   ├── embeddings.py
│   │   │   ├── sparse.py
│   │   │   ├── fusion.py
│   │   │   └── reranker.py
│   │   ├── clients/
│   │   │   ├── qdrant.py
│   │   │   └── llm.py
│   │   ├── main.py
│   │   └── worker.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── documents/
│   │   │   ├── chat/
│   │   │   └── pdf-viewer/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── test/
│   ├── package.json
│   └── Dockerfile
├── eval/
│   ├── corpus/
│   ├── dataset/
│   └── scripts/
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── roadmap.md
│   ├── decisions.md
│   ├── security.md
│   ├── scaling.md
│   ├── interview.md
│   └── eval/
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── compose.yml
├── Makefile
└── README.md
```

The listed structure is the intended end state, not a claim that those modules already exist. Only phase 0 documents are currently present.

## First implementation acceptance criteria

The next phase will create runnable `api` and `worker` service skeletons, environment settings, Dockerfiles with non-root users, Compose services, Makefile commands, a baseline test and GitHub Actions CI. Authentication and retrieval remain out of scope until their respective phases.

## Design-review questions

1. Why is the original extracted text stored separately from normalized retrieval text?
2. Why is PostgreSQL the ownership authority even when Qdrant has a `user_id` payload filter?
3. Why should citation highlighting preserve geometry instead of relying only on normalized character offsets?
