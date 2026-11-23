.PHONY: dev down logs test lint migrate

dev:
	docker compose up --build -d

migrate:
	docker compose exec -T api python -m alembic -c alembic.ini upgrade head

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	python -m pytest backend/tests -q

lint:
	ruff check backend
