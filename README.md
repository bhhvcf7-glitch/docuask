# DocuAsk

Bilingual PDF question answering with citations. **MVP phase 8 and a minimal React frontend are implemented in code.** Authentication, upload, Arabic text extraction, CPU embeddings, Qdrant search, and streaming QA are present. No deployment or end-to-end evaluation metrics are claimed.

## Current capabilities

| Feature | Status |
| --- | --- |
| FastAPI, PostgreSQL, Qdrant, Docker Compose | Implemented; local full-stack smoke test still required |
| Argon2 login and JWT access | Implemented; casefolded email uniqueness enforced by migration |
| Authenticated PDF upload, SHA-256 deduplication | Implemented; failed documents can retry, owner can delete |
| PDF text extraction, Arabic normalization, page-numbered chunks | Implemented; selective PDFium fallback for rejected pages, optional OCR off by default |
| Multilingual-e5-small dense indexing and owner-scoped retrieval | Implemented; semantic quality not yet benchmarked |
| OpenAI-compatible / Ollama LLM providers | Implemented; external model inference not exercised in CI |
| SSE grounded QA, numbered citations mapped to retrieved chunk IDs | Implemented; provider and streaming behavior covered by mocks |
| Refusal for no/low-score evidence and model missing citations | Implemented; threshold not calibrated |
| Client cancellation | Implemented with request-disconnect polling and async stream cleanup |
| Minimal React UI | Implemented; CI TypeScript build and SSE parser tests |
| Deployment | Not implemented |
| Reproducible dense retrieval evaluation | Implemented; 6 original CC0 PDFs, 36 pages, 72 answerable and 12 unanswerable questions; model metrics unmeasured |
| Hit@k / MRR and latency benchmarks | Script ready; measurements pending local run |

[Architecture design](docs/design/architecture.md) · [MVP plan](docs/mvp-plan.md) · [Arabic PDF extraction](docs/arabic-extraction.md) · [Extractor comparison](docs/extraction/comparison.md) · [Historical roadmap](docs/design/roadmap.md)

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

Open `http://localhost:8000/docs`. Register with `POST /auth/register`, log in with `POST /auth/login`, authorize with your Bearer token, upload a text-based PDF via `POST /documents`, and poll `GET /documents/{document_id}` until `ready`. Processing runs in an in-process FastAPI background task. Scanned PDFs require optional OCR (off by default); see the extraction guide.

`POST /search` accepts `{"question":"ما موضوع المستند؟","limit":5}` and returns ranked passages with source pages.

`POST /qa/ask` accepts the same JSON and responds as `text/event-stream`. Use a streaming HTTP client to observe chunks:

```bash
curl -N -X POST http://localhost:8000/qa/ask -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" -d '{"question":"What does this document say?","limit":5}'
```

Events are `token` (`{"text":"..."}`), `citations` (`{"sources":[{"number":1,"chunk_id":"...","document_id":"...","filename":"...","page_number":2,"text":"..."}]}`), `refusal`, `error`, and `done`. The prompt labels retrieved passages [1], [2] and so on; the server maps those source numbers to authorized chunk UUIDs and page numbers. References outside that set are dropped. Text is withheld until the provider supplies at least one valid citation, then streams incrementally. If no valid citation appears, the answer is refused. The backend cannot guarantee claim-by-claim faithfulness; evaluation is required.

## Tests

The new HTTP smoke integration test uses real PostgreSQL and Qdrant with deterministic stand-ins for embeddings and LLM generation. This is not a full Docker/Ollama test; see [smoke test and React setup](docs/local-smoke.md).

```bash
python -m pip install -e './backend[dev]'
python -m ruff check backend
python -m pytest backend/tests -q
```

Integration tests need migrated PostgreSQL and `RUN_DB_TESTS=1`; Qdrant tests also need `RUN_VECTOR_TESTS=1`. GitHub Actions provides both services. LLM HTTP behavior uses fake streams; CI does **not** download weights, run Ollama, call paid APIs, or verify full Docker runtime.

## Limitations

This is a local-development MVP, not a public production service. There is no default OCR engine, refresh token, rate limiting, durable queue, automatic rescheduling after crashes, cache, prompt-injection guarantee, PDF highlighting, or deployed frontend. Cosine similarity threshold `QA_MIN_SCORE=0.45` is an uncalibrated heuristic. On cancellation the server closes the provider stream when possible, but providers may still bill for already processed tokens. Unexpected ingestion errors mark the document failed; a startup sweep marks processing documents older than STALE_PROCESSING_MINUTES as failed. Owners can retry failed documents using POST /documents/{id}/retry or delete queued/failed/ready documents using DELETE /documents/{id}. Delete removes Qdrant points, database state and local PDF when all services are available; these resources do not share a transaction, so a partial cleanup failure may need manual repair. Do not expose the API publicly without hardening.

## Upgrade notes

Run Alembic upgrade before starting the updated API. Migration 0002 normalizes existing email addresses and creates a unique index on lower(email). If multiple accounts collide under lower(trim(email)), the migration stops: resolve them manually before retrying; no user records are merged automatically. Documents now track status_changed_at for stale-job recovery. PDF ingestion normalizes saved chunk text once, while questions are normalized at embedding time. /health is liveness; /ready checks PostgreSQL and Qdrant and is used by the container healthcheck. Model-specific relevance thresholds remain uncalibrated pending evaluation.

## V2 Phase 2: shared resources

During FastAPI lifespan startup, DocuAsk creates one async SQLAlchemy engine/sessionmaker, one Qdrant client, and one vector index. It checks the collection and preloads multilingual-e5-small once per worker; shutdown closes the client and disposes the engine. Ingestion and search use these shared resources rather than opening clients for every request. Startup requires Postgres and Qdrant to be reachable. Set `PRELOAD_EMBEDDINGS=false` to defer model loading for CI or constrained local development; the model is then loaded on first embedding request and shared via a cached loader. The runtime default remains `true`; CI sets `PRELOAD_EMBEDDINGS=false`. With multiple Uvicorn workers, each worker owns its own resources and model instance.

Citations now use short `[1]` or `[2]` tokens in the prompt and model output. The server maps each accepted source number back to its retrieved chunk ID; it does not trust source identifiers supplied by the model. Citation relevance and factual support are not yet measured.

## V2 Phase 3: chunk boundaries

`chunk_pages` emits separate chunks for separate paragraphs, even when both would fit together. Within an oversized paragraph, it packs complete sentences first and uses Arabic (`؟`, `،`, `؛`) and English (`.`, `?`, `!`, `,`, `;`, `:`) punctuation as preferred boundaries. It falls back to words when a sentence alone exceeds the maximum chunk size, and splits oversized individual words only when necessary. Overlap applies only when size forces a split, not across paragraphs or PDF pages. The existing `ordinal`, one-based `page_number`, `original_text` and `normalized_text` fields are unchanged. There is no migration. Sentence splitting is heuristic; abbreviations and extracted PDF layout can still produce imperfect boundaries. Chunking and retrieval accuracy are not yet measured.

## V2 Phase 4: Arabic PDF extraction

Three public Arabic PDF fixtures from jsPDF, PDF.js and Tabula are checked into the test suite. Their real pdfplumber output contains Arabic presentation forms and reversed-order words. The extraction quality check logs presentation forms and rejects high-confidence reversal, disconnected-letter or unmapped-glyph patterns rather than indexing unreliable source text. Selective Unicode NFKC decomposes Arabic presentation forms only in normalized text, never in original citation text. These heuristics can miss errors and do not replace OCR or correct visual reading order. See [observations, provenance and reproduction](docs/arabic-extraction.md). No Arabic CER/WER or retrieval-quality improvement is claimed.

## V2 Phase 5: retrieval evaluation

The public [evaluation corpus and runner](eval/README.md) contain six reproducible, **synthetic** PDF documents (three Arabic, three English, 36 pages), 72 answerable questions labeled with correct document and page, and 12 unanswerable questions. This is a controlled baseline, **not** a representative set of independently published Arabic PDFs. GitHub Actions validates generated PDF text and labels and publishes the six PDFs as a build artifact, without running model inference. Actual dense retrieval measurements require a local CPU run. The script uses the existing pdfplumber, chunker, multilingual-e5-small and Qdrant vector indexing code, with local in-memory Qdrant. LLM answer quality is not measured; the refusal metric measures only the retrieval similarity gate.

| Metric | multilingual-e5-small (dense retrieval) |
| --- | --- |
| hit@1 / hit@3 / hit@5 | Not measured |
| MRR@5 | Not measured |
| Indexed chunk count | Validated in check mode; real-model run pending |
| Unanswerable retrieval-gate refusal accuracy | Not measured |
| Retrieval latency p50 / p95 | Not measured |

To run the real model evaluation: `python -m pip install -e './backend[dev,embeddings]'` and `python -m eval.run --output docs/eval/results.local.json`. The resulting JSON contains per-query rankings, similarity scores and timing measurements. Review those results before adjusting `QA_MIN_SCORE` or the chunk size. See [evaluation details](docs/eval/README.md).

## Arabic PDF extractor comparison

Run `python -m pip install -e './backend[dev,extractor-comparison]'` and
`python scripts/compare_arabic_extractors.py` to compare pdfplumber,
pypdfium2, PyMuPDF and pypdf on the three upstream Arabic PDF fixtures.
The script saves raw text samples, inspector warnings and first-page reference
phrase checks as JSON and Markdown. Production uses pdfplumber first and a
pypdfium2 fallback only for pages the inspector rejects or cannot extract.
PyMuPDF is AGPL-3.0 or commercially licensed and is **not** installed by
default. Read [the comparison method and licensing notes](docs/extraction/comparison.md)
before adopting any extractor.

## Arabic extraction fallback and OCR

The [Arabic extraction guide](docs/arabic-extraction.md) explains the measured
three-fixture PDFium fallback, its limitations, and the optional
`OCR_ENABLED=false` setting. Enabling OCR requires `backend[ocr]`, Tesseract
and the `ara+eng` language packs installed on the host; the stock Docker image
does not include them. No general Arabic extraction accuracy gain is claimed.

## License

[MIT](LICENSE).

## Optional hybrid retrieval

Set `RETRIEVAL_MODE=hybrid` and apply Alembic migrations. Dense retrieval remains the default. See [hybrid retrieval design](docs/hybrid-retrieval.md).

## Optional multilingual reranking

Set `RERANK_ENABLED=true` with the embeddings extra installed. See [reranking and evaluation](docs/reranking.md).

## Grounded QA citation validation

Answers are buffered and structurally validated before SSE release. Each claim must end with valid retrieved source numbers; invalid, missing or incomplete references cause refusal. See [limitations and contract](docs/grounded-qa.md).

## Conversation memory

Authenticated clients can create, list, read and delete conversations. Pass `conversation_id` to `/qa/ask` to rewrite follow-up questions using recent questions. See [conversation memory](docs/conversations.md).

## Interactive source viewer

Open a citation to render its original page with exact word-coordinate highlights when available. See [viewer limitations](docs/pdf-viewer.md).
