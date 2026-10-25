"""API de infraestructura del POC; las operaciones se ejecutan por CLI."""

from fastapi import FastAPI

from ivostock.db import database, execute

app = FastAPI(title="Ivo Stock", version="0.1.0")


@app.get("/health")
def health():
    with database().connect() as conn:
        execute(conn, "SELECT 1 FROM alembic_version")
    return {"status": "ok"}
