FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/model-cache

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir '.[embeddings]' \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage /app/model-cache \
    && chown -R appuser:appuser /app/storage /app/model-cache

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=8s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=5).close()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
