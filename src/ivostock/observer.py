"""Observador externo de sólo lectura: HTTP, sin PostgreSQL, archivos ni estado durable."""

import os
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ivostock.api_errors import SafeRoute
from ivostock.probes import http_components

app = FastAPI(title="Ivo Stock · Observador", docs_url=None, redoc_url=None, openapi_url=None)
app.router.route_class = SafeRoute
bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def read(path, authorization, params=None):
    if not authorization:
        raise HTTPException(401, "No autenticado")
    try:
        response = httpx.get(
            os.getenv("METRICS_URL", "http://metrics:8002") + path,
            headers={"Authorization": authorization},
            params=params,
            timeout=10,
        )
        if response.status_code in (401, 403):
            raise HTTPException(401, "No autenticado")
        if response.status_code == 422:
            raise HTTPException(422, "Período inválido: usar minutos completos y hasta siete días")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Estado de métricas no disponible") from None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def observe(
    credentials: Credentials,
    start: str | None = None,
    end: str | None = None,
):
    authorization = f"Bearer {credentials.credentials}" if credentials else None
    params = {key: value for key, value in (("start", start), ("end", end)) if value}
    state = read("/metrics/current", authorization)
    period = read("/metrics/summary", authorization, params)
    return {"current": state, "summary": period, "http_components": http_components()}


@app.get("/openapi.json", include_in_schema=False)
def schema(credentials: Credentials):
    authorization = f"Bearer {credentials.credentials}" if credentials else None
    read("/auth/me", authorization)
    return app.openapi()
