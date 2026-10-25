.PHONY: up down test check
up:
	python scripts/configurar.py
	docker compose up --build -d --wait
down:
	docker compose down
test:
	uv run pytest -q -m "not integration"
check:
	uv run ruff check .
	uv run python scripts/verificar_documentacion.py
	uv run python scripts/verificar_secretos.py
