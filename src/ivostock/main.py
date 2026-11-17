"""API de Ivo Stock (RNF-11).

Los únicos endpoints de datos públicos son `GET /health` y `POST /auth/login`. Además se sirve la
interfaz estática (ADR-0013): `/` y `/static/*` son públicos porque son sólo la página de login y
sus recursos, sin datos operativos; todo dato llega por la API con sesión de operador.

Swagger UI y ReDoc están apagados y el esquema OpenAPI sólo se entrega con sesión de operador
(`GET /openapi.json`): el contrato de la API no es público (ADR-0014).

Todo router de configuración declara `require_operator` y usa `SafeRoute`, que traduce los
errores sin revelar detalles internos.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ivostock import api_auth, api_config
from ivostock.api_auth import require_operator
from ivostock.db import database, execute
from ivostock.logs import configurar


@asynccontextmanager
async def lifespan(app):
    configurar()  # Registros JSON en stderr; sin esto no se emiten los INFO de auditoría.
    yield


app = FastAPI(
    title="Ivo Stock",
    version="0.4.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(api_auth.router)
app.include_router(api_config.router)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Sin `input`: el valor recibido puede ser una contraseña o una URL con credenciales.
    errors = [{"type": e["type"], "loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": errors}, status_code=422)


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(require_operator)])
def openapi_schema():
    # `openapi_url=None` quita la ruta pública por defecto; ésta exige sesión (RNF-11, RNF-16).
    return app.openapi()


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


# --- Interfaz estática (RF-25, ADR-0013) ------------------------------------------------------
# Dentro del paquete: la ruta no depende del directorio de trabajo y viaja con la instalación
# (la imagen usa `uv sync --no-editable`). Ninguna de estas rutas figura en OpenAPI.

STATIC_DIR = Path(__file__).resolve().parent / "static"
INTERFACE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Content-Type-Options": "nosniff",
    # Sin scripts ni estilos en línea: una inyección de HTML no puede ejecutar código.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def interface():
    return FileResponse(STATIC_DIR / "index.html", headers=INTERFACE_HEADERS)
