"""Servicio interno: persiste estado cada minuto, independiente de la API principal."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError

from ivostock import api_auth, api_metrics, metrics
from ivostock.api_auth import require_operator
from ivostock.api_errors import SafeRoute, invalid_request
from ivostock.db import database
from ivostock.logs import configurar

log = logging.getLogger("ivostock.metrics")


async def collect():
    while True:
        try:
            await asyncio.to_thread(metrics.sample, database())
        except Exception as exc:
            # No se registran URLs, SQL ni credenciales. Se reintenta en el próximo minuto.
            log.error(
                "Muestra no registrada", extra={"component": "metrics", "error": type(exc).__name__}
            )
        await asyncio.sleep(60 - datetime.now(UTC).timestamp() % 60)


@asynccontextmanager
async def lifespan(app):
    configurar()
    task = asyncio.create_task(collect())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Ivo Stock · Métricas", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
)
app.router.route_class = SafeRoute
# Reutiliza la validación de sesión, sin abrir otro punto de login ni de logout.
app.add_api_route("/auth/me", api_auth.me, methods=["GET"], responses=api_auth.UNAUTHENTICATED)
app.include_router(api_metrics.router)
app.add_exception_handler(RequestValidationError, invalid_request)


@app.get("/health")
def health():
    # Liveness del servicio: el estado y su antigüedad se consultan con sesión.
    return {"status": "ok"}


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(require_operator)])
def schema():
    return app.openapi()
