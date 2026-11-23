# DocuAsk

Bilingual, citation-grounded document question answering. Project status: MVP phase 2 configuration and logging implemented. Database models, authentication, ingestion, retrieval, and QA are not yet implemented.

## Problem

Users need answers from PDF, DOCX, TXT, and Markdown documents in Arabic, English, or both. A credible answer must identify the source document and passage rather than merely sound plausible. Arabic PDFs introduce extraction errors, mixed directionality, and orthographic variants that change retrieval quality.

## Intended capabilities

- Account-based document and chat isolation.
- Validated uploads with asynchronous, retryable ingestion.
- Arabic-aware parsing, preservation of original source text, and normalized retrieval text.
- Dense/sparse hybrid retrieval using reciprocal rank fusion and optional cross-encoder reranking.
- Answers constrained to retrieved evidence, validated source references, and explicit refusal for insufficient evidence.
- Streaming UI and PDF citation navigation with passage highlights when reliable offsets/bounding boxes are available.
- Reproducible retrieval evaluation rather than synthetic benchmark claims.

## Architecture

```mermaid
flowchart LR
    UI["React / Vite UI"] --> API["FastAPI API"]
    API --> DB[(PostgreSQL)]
    API --> REDIS[(Redis)]
    REDIS --> WORKER["ARQ worker"]
    WORKER --> PARSE["Parse + OCR + normalize + chunk"]
    PARSE --> EMB["Embedding worker"]
    EMB --> QDRANT[(Qdrant)]
    API --> SEARCH["Dense + sparse retrieval / RRF"]
    QDRANT --> SEARCH
    SEARCH --> RERANK["Optional reranker"]
    RERANK --> GEN["Grounded LLM provider"]
    GEN --> VERIFY["Validate cited chunk IDs"]
    VERIFY --> API
    API --> UI
```

See [architecture](docs/architecture.md), [data model](docs/data-model.md), [MVP phase plan](docs/mvp-plan.md), and the [original design roadmap](docs/roadmap.md). The original architecture describes the eventual system, not the current implementation.

## Technology decisions

Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL, Redis/ARQ, Qdrant, multilingual-e5 with a benchmarked bge-m3 alternative, optional multilingual cross-encoder, configurable OpenAI-compatible/Ollama providers, React/TypeScript/Vite/Tailwind, TanStack Query, React Router, react-pdf, SSE, Prometheus, structlog, pytest and Vitest.

## Status and verification

| Item | State |
| --- | --- |
| Architecture and data design | Drafted; MVP plan supersedes original delivery order |
| FastAPI /health and OpenAPI schema | Implemented; tested in GitHub CI |
| Docker Compose API, PostgreSQL, Qdrant | Defined with env-based configuration; container startup not verified here |
| GitHub Actions Ruff/pytest | CI workflow enabled; see Actions for current run results |
| Pydantic Settings and structlog | Implemented with configuration and request-log tests |
| MIT LICENSE | Added |
| API and authentication | Not implemented |
| Upload and worker | Not implemented |
| Retrieval and answer generation | Not implemented |
| UI | Not implemented |
| Evaluation results | Not measured |
| Deployment | Not deployed |

**This is a working API skeleton, not yet a document Q&A application.** No evaluation metrics or live deployment URLs are claimed.

## Local development (phase 2)

Requires Python 3.11, Docker Engine with the Compose plugin, and Make (Git Bash or WSL on Windows). Create a local env file before starting the stack:

```bash
cp .env.example .env
# Change POSTGRES_PASSWORD in .env to a unique local password.
make dev
curl http://localhost:8000/health
```

Expected health JSON: `{"status":"ok"}`. OpenAPI docs: `http://localhost:8000/docs`. PostgreSQL and Qdrant are internal Compose services at this stage; the API does not access them yet.

For local checks:

```bash
python -m pip install -e './backend[dev]'
make lint
make test
```

Stop containers with `make down`. Docker Compose startup was not executed in the authoring environment because Docker was unavailable; verify it locally. PostgreSQL credentials are read from the uncommitted .env file; the example value is for local setup only. Changing credentials after initializing a database volume does not update the existing PostgreSQL user password. Remove the volume only if you intend to destroy local data.

## Evaluation table

The planned comparison will be populated only after local runs over a versioned bilingual dataset.

| Retrieval configuration | Hit@5 | MRR@10 | Latency p50 / p95 |
| --- | --- | --- | --- |
| Dense only | Not measured | Not measured | Not measured |
| Sparse only | Not measured | Not measured | Not measured |
| Hybrid RRF | Not measured | Not measured | Not measured |
| Hybrid + reranker | Not measured | Not measured | Not measured |

## Known limitations

Design only. PDF text highlighting is not guaranteed by character offsets alone: precise text-layer spans or bounding-box mapping must be retained during extraction. OCR text alignment will need a separate mapping and confidence tracking. LLM citations require backend validation and cannot prove every individual claim without further evidence checks.

## Demo

Demo GIF: pending first usable release.

## License

Licensed under the [MIT License](LICENSE).
