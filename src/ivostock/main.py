"""API de Ivo Stock. Sólo `/health` y `POST /auth/login` son públicos (RNF-11).

Todo router de configuración declara `require_operator` y usa `SafeRoute`, que traduce los
errores sin revelar detalles internos.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ivostock import api_auth, api_config
from ivostock.db import database, execute
from ivostock.logs import configurar


@asynccontextmanager
async def lifespan(app):
    configurar()  # Registros JSON en stderr; sin esto no se emiten los INFO de auditoría.
    yield


app = FastAPI(title="Ivo Stock", version="0.3.0", lifespan=lifespan)
app.include_router(api_auth.router)
app.include_router(api_config.router)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Sin `input`: el valor recibido puede ser una contraseña o una URL con credenciales.
    errors = [{"type": e["type"], "loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": errors}, status_code=422)


@app.get(
    "/health",
    tags=["health"],
    summary="Estado del servicio",
    description="Público. Sólo confirma que la API y la base responden; no expone datos operativos.",
)
def health():
    with database().connect() as conn:
        execute(conn, "SELECT 1 FROM alembic_version")
    return {"status": "ok"}
