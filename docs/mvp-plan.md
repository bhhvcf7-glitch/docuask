# MVP plan (supersedes the original 26-phase implementation order)

1. FastAPI repository skeleton, Docker Compose for API/PostgreSQL/Qdrant, Makefile and lint/test CI.
2. Pydantic settings, structlog, `.env.example` and MIT license.
3. SQLAlchemy async and Alembic: users, documents and chunks only.
4. Argon2 registration/login and JWT access tokens.
5. PDF upload validation, local storage and per-user SHA-256 deduplication.
6. Page extraction, Arabic normalization, paragraph chunking and FastAPI background ingestion.
7. Multilingual-e5 dense embeddings, Qdrant search and mandatory tenant filter.
8. Grounded question-answering with OpenAI-compatible/Ollama providers, SSE, citation validation and refusal.

Then: React upload/chat/source UI; evaluation dataset and hit@k/MRR; sparse/RRF; reranking; OCR; refresh tokens; Redis queue; cache; metrics; PDF highlighting; deployment.

The original docs remain design references, not claims about implemented functionality. No benchmark numbers have been measured.
