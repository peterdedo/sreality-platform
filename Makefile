.PHONY: up down logs migrate seed scrape test lint build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python scripts/seed.py

scrape:
	docker compose exec backend python -c "import asyncio; from sqlmodel import Session; from app.core.db import engine; from app.scraping.pipeline import run_incremental_scrape; asyncio.run(run_incremental_scrape(Session(engine)))"

test:
	docker compose exec backend pytest

lint:
	docker compose exec frontend npm run lint

build:
	docker compose build
