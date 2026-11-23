# DocuAsk

Bilingual PDF question answering with citations. **MVP phase 8 and a minimal React frontend are implemented in code.** Authentication, upload, Arabic text extraction, CPU embeddings, Qdrant search, and streaming QA are present. No deployment or end-to-end evaluation metrics are claimed.

## Current capabilities

| Feature | Status |
| --- | --- |
| FastAPI, PostgreSQL, Qdrant, Docker Compose | Implemented; local full-stack smoke test still required |
| Argon2 login and JWT access | Implemented; casefolded email uniqueness enforced by migration |
| Authenticated PDF upload, SHA-256 deduplication | Implemented; failed documents can retry, owner can delete |
| PDF text extraction, Arabic normalization, page-numbered chunks | Implemented |
| Multilingual-e5-small dense indexing and owner-scoped retrieval | Implemented; semantic quality not yet benchmarked |
| OpenAI-compatible / Ollama LLM providers | Implemented; external model inference not exercised in CI |
| SSE grounded QA, validated chunk IDs, source page numbers | Implemented; provider and streaming behavior covered by mocks |
| Refusal for no/low-score evidence and model missing citations | Implemented; threshold not calibrated |
| Client cancellation | Implemented with request-disconnect polling and async stream cleanup |
| Minimal React UI | Implemented; CI TypeScript build and SSE parser tests |
| Deployment | Not implemented |
| Hit@k / MRR and latency benchmarks | Not measured |

[Architecture design](docs/design/architecture.md) · [MVP plan](docs/mvp-plan.md) · [Historical roadmap](docs/design/roadmap.md)

## Run on Windows

Requirements: Python 3.11, Docker Desktop with Compose and enough disk space for PyTorch, sentence-transformers and e5 model weights.

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d postgres qdrant
docker compose build api
docker compose run --rm --no-deps api python -m alembic -c alembic.ini upgrade head
docker compose up -d api
```

Set unique `POSTGRES_PASSWORD` and `JWT_SECRET` in `.env` before starting. `JWT_SECRET` must contain at least 32 characters. No secrets should be committed.

For **Ollama** (default), install and run Ollama on your computer and pull the configured model:

```powershell
ollama pull llama3.2:3b
```

Compose uses `http://host.docker.internal:11434` for the host Ollama service. Verify the container can reach that service; Ollama may need to bind beyond loopback depending on your Docker setup. Never expose Ollama publicly.

Alternatively, set in `.env`:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your-own-api-key
```

Restart the API after changing the environment. An OpenAI-compatible provider must implement `/chat/completions` streaming.

### API workflow

Open `http://localhost:8000/docs`. Register with `POST /auth/register`, log in with `POST /auth/login`, authorize with your Bearer token, upload a text-based PDF via `POST /documents`, and poll `GET /documents/{document_id}` until `ready`. Processing runs in an in-process FastAPI background task. Scanned PDFs have no OCR support and fail ingestion.

`POST /search` accepts `{"question":"ما موضوع المستند؟","limit":5}` and returns ranked passages with source pages.

`POST /qa/ask` accepts the same JSON and responds as `text/event-stream`. Use a streaming HTTP client to observe chunks:

```bash
curl -N -X POST http://localhost:8000/qa/ask -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" -d '{"question":"What does this document say?","limit":5}'
```

Events are `token` (`{"text":"..."}`), `citations` (`{"sources":[{"number":1,"chunk_id":"...","document_id":"...","filename":"...","page_number":2,"text":"..."}]}`), `refusal`, `error`, and `done`. The backend only emits numbered citations for IDs returned in its own retrieval results; invented IDs are dropped. Text is withheld until the provider supplies at least one valid citation, then streams incrementally. If no valid citation appears, the answer is refused. The backend cannot guarantee claim-by-claim faithfulness; evaluation is required.

## Tests

The new HTTP smoke integration test uses real PostgreSQL and Qdrant with deterministic stand-ins for embeddings and LLM generation. This is not a full Docker/Ollama test; see [smoke test and React setup](docs/local-smoke.md).\n\n
```bash
python -m pip install -e './backend[dev]'
python -m ruff check backend
python -m pytest backend/tests -q
```

Integration tests need migrated PostgreSQL and `RUN_DB_TESTS=1`; Qdrant tests also need `RUN_VECTOR_TESTS=1`. GitHub Actions provides both services. LLM HTTP behavior uses fake streams; CI does **not** download weights, run Ollama, call paid APIs, or verify full Docker runtime.

## Limitations

This is a local-development MVP, not a public production service. There is no OCR, refresh token, rate limiting, durable queue, automatic rescheduling after crashes, cache, prompt-injection guarantee, PDF highlighting, or deployed frontend. Cosine similarity threshold `QA_MIN_SCORE=0.45` is an uncalibrated heuristic. On cancellation the server closes the provider stream when possible, but providers may still bill for already processed tokens. Unexpected ingestion errors mark the document failed; a startup sweep marks processing documents older than STALE_PROCESSING_MINUTES as failed. Owners can retry failed documents using POST /documents/{id}/retry or delete queued/failed/ready documents using DELETE /documents/{id}. Delete removes Qdrant points, database state and local PDF when all services are available; these resources do not share a transaction, so a partial cleanup failure may need manual repair. Do not expose the API publicly without hardening.

## Upgrade notes

Run Alembic upgrade before starting the updated API. Migration 0002 normalizes existing email addresses and creates a unique index on lower(email). If multiple accounts collide under lower(trim(email)), the migration stops: resolve them manually before retrying; no user records are merged automatically. Documents now track status_changed_at for stale-job recovery. PDF ingestion normalizes saved chunk text once, while questions are normalized at embedding time. /health is liveness; /ready checks PostgreSQL and Qdrant and is used by the container healthcheck. Model-specific relevance thresholds remain uncalibrated pending evaluation.

## License

[MIT](LICENSE).
