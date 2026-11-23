FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage \
    && chown appuser:appuser /app/storage

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
