.PHONY: dev down logs test lint

dev:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	python -m pytest backend/tests -q

lint:
	ruff check backend
