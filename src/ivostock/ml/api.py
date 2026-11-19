"""Serving privado del detector global. Ninguna ruta modifica el modelo."""

import hmac
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ivostock.db import database, rows
from ivostock.logs import configurar
from ivostock.ml.contracts import ClassificationIn, ClassificationOut
from ivostock.ml.repository import active_model


@asynccontextmanager
async def lifespan(app):
    configurar()
    yield


app = FastAPI(title="Ivo Stock ML (interno)", docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=lifespan)


def require_service(authorization: Annotated[str, Header()] = ""):
    token = os.getenv("ML_TOKEN", "")
    if not token or not hmac.compare_digest(authorization.encode(), ("Bearer " + token).encode()):
        raise HTTPException(401, "No autorizado")


def load_model():
    try:
        return active_model(database())
    except (ValueError, KeyError, TypeError, OverflowError):
        raise HTTPException(503, "invalid_model") from None


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse({"detail": "Solicitud ML inválida"}, status_code=422)


@app.exception_handler(Exception)
@app.exception_handler(SQLAlchemyError)
async def internal_error(request, exc):
    # Nunca emitir URLs, credenciales, vectores ni mensajes de excepciones externas.
    return JSONResponse({"detail": "Servicio ML no disponible"}, status_code=503)


@app.get("/health/live")
def live():
    with database().connect() as conn:
        rows(conn, "SELECT 1 FROM ml_state WHERE id=1")
    return {"status": "ok"}


@app.get("/health")
def ready():
    model = load_model()
    if model is None:
        raise HTTPException(503, "not_ready")
    # Sonda funcional de aritmética e inferencia con una entrada almacenada del modelo.
    with database().begin() as conn:
        probe = rows(conn, "SELECT provider_id,features FROM ml_observations "
                     "WHERE run_id=ANY(:ids) ORDER BY run_id", ids=model.payload["run_ids"])
    probe = next((p for p in probe if model.ready(p["provider_id"])), None)
    if probe is None:
        raise HTTPException(503, "not_ready")
    model.classify(probe["provider_id"], probe["features"])
    return {"status": "ok"}


@app.get("/health/training")
def training_health():
    with database().begin() as conn:
        found = rows(conn, "SELECT 1 FROM worker_heartbeats WHERE name='ml-train' "
                     "AND at>now()-interval '30 seconds'")
    if not found:
        raise HTTPException(503, "not_ready")
    return {"status": "ok"}


@app.post("/classify", response_model=ClassificationOut, dependencies=[Depends(require_service)])
def classify(body: ClassificationIn):
    model = load_model()
    if model is None or not model.ready(body.provider_id):
        raise HTTPException(503, "insufficient_history")
    return model.classify(body.provider_id, body.metrics)
