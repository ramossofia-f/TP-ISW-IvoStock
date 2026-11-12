"""API de configuración: proveedores, tiendas, vínculos y corridas (RF-02, RF-03, RF-05..RF-09, RF-25).

Cada endpoint delega en `ivostock.services`, la misma capa que usa la CLI. Todo el router exige
sesión de operador. Quedan fuera a propósito los comandos de ensayo y operación interna
(`fault`, `schedule-now`, `monitor`, `compare`, `publish`): no son acciones de usuario.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from ivostock import services
from ivostock.api_auth import require_operator
from ivostock.api_errors import SafeRoute
from ivostock.api_models import (
    BIGINT_MAX,
    STORE_ID,
    ApproveIn,
    ApproveOut,
    AvailableStore,
    DisableOut,
    ErrorOut,
    LinkOffOut,
    LinkResumeOut,
    LinksPage,
    LinkSummary,
    ProviderCreated,
    ProviderIn,
    ProviderOut,
    RunsPage,
    RunSummary,
    StoreIn,
    StoreOut,
    SuggestionsOut,
)
from ivostock.db import database

COMMON = {
    401: {"model": ErrorOut, "description": "Sin sesión válida"},
    500: {"model": ErrorOut, "description": "Error interno; no se detalla la causa"},
}
router = APIRouter(
    route_class=SafeRoute, dependencies=[Depends(require_operator)], responses=COMMON
)

ProviderId = Annotated[int, Path(ge=1, le=BIGINT_MAX, description="Id del proveedor")]
LinkId = Annotated[int, Path(ge=1, le=BIGINT_MAX, description="Id del vínculo")]
StoreQuery = Annotated[str, Query(pattern=STORE_ID, description="Id de la tienda")]
OptionalStore = Annotated[str | None, Query(pattern=STORE_ID, description="Filtrar por tienda")]
NOT_FOUND = {404: {"model": ErrorOut, "description": "No existe"}}
CONFLICT = {409: {"model": ErrorOut, "description": "Choca con el estado actual"}}


# --- Proveedores ---------------------------------------------------------------------------


@router.post(
    "/providers",
    status_code=201,
    response_model=ProviderCreated,
    tags=["providers"],
    summary="Dar de alta un proveedor",
    description="Descarga la fuente y valida el contrato `SKU;stock`. Devuelve los SKU válidos, "
    "la tasa de errores de parseo con su alerta, una muestra, la próxima ingesta y las "
    "publicaciones sugeridas por tienda. La primera ingesta ocurre en su horario.",
    responses={
        409: {"model": ErrorOut, "description": "Ya existe un proveedor con ese nombre"},
        422: {"model": ErrorOut, "description": "La fuente incumple el contrato"},
        502: {"model": ErrorOut, "description": "No se pudo descargar la fuente"},
    },
)
def create_provider(body: ProviderIn):
    result = services.add_provider(database(), body.name, body.url)
    preview = [{"sku": sku, "stock": stock} for sku, stock in result["preview"]]
    return {**result, "preview": preview}


@router.get(
    "/providers",
    response_model=list[ProviderOut],
    tags=["providers"],
    summary="Listar proveedores",
    description="No incluye la URL configurada.",
)
def list_providers():
    return services.status(database(), "providers")


@router.post(
    "/providers/{provider_id}/disable",
    status_code=202,
    response_model=DisableOut,
    tags=["providers"],
    summary="Dar de baja un proveedor",
    description="Lleva a cero todos sus vínculos antes de desactivarlo (INV-3). La confirmación "
    "es asíncrona: la respuesta indica cuántos cortes se ordenaron.",
    responses={**NOT_FOUND, 409: {"model": ErrorOut, "description": "Ya está dado de baja"}},
)
def disable_provider(provider_id: ProviderId):
    engine = database()
    services.require_provider(engine, provider_id)
    return {"provider": provider_id, **services.cut(engine, provider_id)}


@router.get(
    "/providers/{provider_id}/suggestions",
    response_model=SuggestionsOut,
    tags=["links"],
    summary="Sugerir publicaciones para vincular",
    description="Cruza el inventario del proveedor con el catálogo de la tienda por SKU y "
    "excluye publicaciones que ya tienen un vínculo activo. Usa el último inventario "
    "aceptado: no descarga nada. `total` cuenta todas; `items` se limita a `limit`.",
    responses={**NOT_FOUND, **CONFLICT},
)
def suggest_links(
    provider_id: ProviderId,
    store: StoreQuery,
    sku: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    positive_only: bool = False,
):
    engine = database()
    services.require_provider(engine, provider_id)
    services.require_store(engine, store, imported=True)
    found = services.suggestions(engine, provider_id, store, sku, positive_only)
    return {"total": len(found), "items": found[:limit]}


@router.post(
    "/providers/{provider_id}/approve",
    response_model=ApproveOut,
    tags=["links"],
    summary="Aprobar vínculos",
    description="Crea vínculos para todas las sugerencias (`all`), publicaciones concretas "
    "(`items`) o las primeras N (`count`). Una publicación con vínculo activo se rechaza "
    "(RF-07): con `items` falla toda la petición y no se crea nada.",
    responses={**NOT_FOUND, **CONFLICT},
)
def approve_links(provider_id: ProviderId, body: ApproveIn):
    engine = database()
    services.require_provider(engine, provider_id)
    services.require_store(engine, body.store, imported=True)
    return services.approve(
        engine,
        provider_id,
        body.store,
        items=body.items,
        count=body.count,
        positive_only=body.positive_only,
    )


# --- Tiendas -------------------------------------------------------------------------------


@router.get(
    "/stores",
    response_model=list[StoreOut],
    tags=["stores"],
    summary="Listar tiendas con el progreso de importación",
)
def list_stores():
    return services.list_stores(database())


@router.get(
    "/stores/available",
    response_model=list[AvailableStore],
    tags=["stores"],
    summary="Tiendas disponibles para incorporar",
    description="Las del marketplace con credenciales preconfiguradas, indicando cuáles ya "
    "fueron incorporadas.",
)
def available_stores():
    return services.available_stores(database())


@router.post(
    "/stores",
    status_code=201,
    response_model=StoreOut,
    tags=["stores"],
    summary="Incorporar una tienda",
    description="Registra una tienda existente en el marketplace e inicia en segundo plano la "
    "importación de su catálogo; el progreso se consulta en `GET /stores`. Nunca crea la "
    "tienda: debe figurar en `GET /stores/available` y existir en el marketplace. Si ya estaba "
    "incorporada responde 200 con su estado. Reutiliza los inventarios ya ingeridos: no "
    "descarga a los proveedores de nuevo.",
    responses={
        200: {"model": StoreOut, "description": "La tienda ya estaba incorporada"},
        404: {
            "model": ErrorOut,
            "description": "La tienda no está disponible para incorporar o no existe en el marketplace",
        },
        502: {"model": ErrorOut, "description": "No se pudo consultar el marketplace"},
    },
)
def add_store(body: StoreIn, response: Response):
    store, created = services.incorporate_store(database(), body.store)
    if not created:
        response.status_code = 200
    return services.store_summary(store)


# --- Vínculos ------------------------------------------------------------------------------


@router.get(
    "/links/summary",
    response_model=LinkSummary,
    tags=["links"],
    summary="Resumen de vínculos",
    responses=NOT_FOUND,
)
def links_summary(store: OptionalStore = None):
    engine = database()
    if store is not None:
        services.require_store(engine, store)
    return services.status(engine, "links", store, summary=True)


@router.get(
    "/links",
    response_model=LinksPage,
    tags=["links"],
    summary="Listar vínculos paginados",
    description="Ordenados por id. Para la página siguiente usar `next_offset`.",
    responses=NOT_FOUND,
)
def list_links(
    store: OptionalStore = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000_000)] = 0,
):
    engine = database()
    if store is not None:
        services.require_store(engine, store)
    return services.list_links(engine, store, limit, offset)


@router.post(
    "/links/{link_id}/off",
    status_code=202,
    response_model=LinkOffOut,
    tags=["links"],
    summary="Apagar un vínculo",
    description="Conserva la intención de cero hasta que el marketplace la confirma; el "
    "vínculo pasa a inactivo recién entonces.",
    responses={**NOT_FOUND, 409: {"model": ErrorOut, "description": "Ya está desactivado"}},
)
def turn_off_link(link_id: LinkId):
    return {"link": link_id, **services.cut_link(database(), link_id)}


@router.post(
    "/links/{link_id}/resume",
    response_model=LinkResumeOut,
    tags=["links"],
    summary="Reanudar un vínculo",
    description="Vuelve a encolar la publicación de un vínculo fallido con el valor vigente "
    "de su proveedor.",
    responses={**NOT_FOUND, 409: {"model": ErrorOut, "description": "El vínculo está inactivo"}},
)
def resume_link(link_id: LinkId):
    return services.resume(database(), link_id)


# --- Corridas (tablero de RF-25) -------------------------------------------------------------


@router.get(
    "/runs/summary",
    response_model=RunSummary,
    tags=["runs"],
    summary="Resumen de corridas por estado",
    responses=NOT_FOUND,
)
def runs_summary(provider: Annotated[int | None, Query(ge=1, le=BIGINT_MAX)] = None):
    engine = database()
    if provider is not None:
        services.require_provider(engine, provider, active=False)
    return services.runs_summary(engine, provider)


@router.get(
    "/runs",
    response_model=RunsPage,
    tags=["runs"],
    summary="Listar corridas de ingesta",
    description="La más reciente primero. Sólo lectura: las corridas las dispara el horario de "
    "cada proveedor. Para la página siguiente usar `next_offset`.",
    responses=NOT_FOUND,
)
def list_runs(
    provider: Annotated[
        int | None, Query(ge=1, le=BIGINT_MAX, description="Filtrar por proveedor")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10_000_000)] = 0,
):
    engine = database()
    if provider is not None:
        services.require_provider(engine, provider, active=False)
    return services.list_runs(engine, provider, limit, offset)
