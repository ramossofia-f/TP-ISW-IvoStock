"""Una única API de lectura del estado, reutilizada por la aplicación y por metrics."""

from datetime import datetime

from fastapi import APIRouter, Depends

from ivostock import metrics
from ivostock.api_auth import require_operator
from ivostock.api_errors import SafeRoute
from ivostock.api_models import ErrorOut
from ivostock.db import database

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    route_class=SafeRoute,
    dependencies=[Depends(require_operator)],
    responses={401: {"model": ErrorOut}, 500: {"model": ErrorOut}},
)


@router.get("/current", summary="Último estado persistido y heartbeats actuales")
def current():
    return metrics.current(database())


@router.get("/history", summary="Muestras por minuto del período; retención de siete días")
def history(start: datetime | None = None, end: datetime | None = None):
    return metrics.history(database(), start, end)


@router.get("/summary", summary="Disponibilidad y percentiles por tienda, sin alertas")
def summary(start: datetime | None = None, end: datetime | None = None):
    return metrics.summary(database(), start, end)
