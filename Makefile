.PHONY: up down install lint test init-db probar ingest corridas gen-feed

PROVEEDOR ?= celesa

up:
	docker compose up -d

down:
	docker compose down

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests

test:
	pytest

init-db:
	python -m ivostock.ingesta init-db

probar:
	python -m ivostock.ingesta probar --proveedor $(PROVEEDOR)

ingest:
	python -m ivostock.ingesta correr --proveedor $(PROVEEDOR)

corridas:
	python -m ivostock.ingesta corridas --proveedor $(PROVEEDOR)

gen-feed:
	python -m ivostock.generador.feeds $(ARGS)
