# Local smoke test and React UI

## What CI verifies

The backend integration test `backend/tests/test_api_smoke.py` exercises register, login,
HTTP PDF upload, FastAPI background ingestion, PostgreSQL, Qdrant, search and SSE answers.
PostgreSQL and Qdrant are real CI services. The embedding model and LLM are replaced with
deterministic test implementations; no external model inference occurs. The test also verifies
that a second user cannot read the first user's document or retrieve its passages.

GitHub Actions validates Docker Compose configuration but does not build or start
the complete ML-heavy Compose stack. That remains a separate local smoke test.

## Full local Docker smoke test

Use Docker Desktop, Python 3.11 and a running Ollama model or configured
OpenAI-compatible provider. Configure secrets in `.env` using `.env.example`.
Do not commit your credentials.

```powershell
git pull origin main
docker compose up -d postgres qdrant
docker compose build api
docker compose run --rm --no-deps api python -m alembic -c alembic.ini upgrade head
docker compose up -d api
py -3.11 -m pip install -e "./backend[dev]"
py -3.11 scripts/smoke_docker.py
```

This script creates a temporary test account and uploads a generated one-page
PDF. It checks the document reaches `ready`, retrieval returns page 1,
and the streamed answer contains source IDs from retrieval. It fails loudly
if the provider refuses to cite, if indexing breaks, or if the model is not
running. The test account remains in the development database.

The first run may download multilingual-e5 model weights and build a large
PyTorch image. Model inference, OCR quality, citation faithfulness and latency
have not been measured by CI.

## React frontend

From a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies API requests to
`http://127.0.0.1:8000`. The UI supports Arabic RTL and English LTR,
registration/login, authenticated PDF upload and status polling, SSE chat,
abort, and sources with document names and page numbers.

The JWT stays in browser memory and is cleared on refresh, rather than
being persisted in localStorage. This is a minimal development UI without
refresh tokens or hosted deployment. Uploads and search remain restricted
to authenticated users.

Run frontend checks:

```powershell
npm run build
npm test
```

For development, no CORS change is needed: API calls use Vite's same-origin
proxy. A production reverse proxy and deployment configuration are future work.
