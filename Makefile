.PHONY: up down test

up:
	docker compose up -d

down:
	docker compose down

test:
	PYTHONPATH=. pytest tests/
