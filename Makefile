.PHONY: up down test check provision
up:
	python scripts/configurar.py
	docker compose up --build -d --wait
provision:
	docker compose run --rm cli python scripts/provisionar_tiendas.py
down:
	docker compose down
test:
	uv run pytest -q -m "not integration"
check:
	uv run ruff check .
	uv run python scripts/verificar_documentacion.py
	uv run python scripts/verificar_secretos.py
