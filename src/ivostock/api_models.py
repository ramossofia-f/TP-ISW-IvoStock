"""Contratos de entrada y salida de la API de configuración (RNF-16)."""

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

# Identificador de tienda: se usa como segmento de ruta hacia el marketplace.
STORE_ID = r"^[A-Za-z0-9_-]{1,32}$"
StoreId = Annotated[str, StringConstraints(pattern=STORE_ID)]
BIGINT_MAX = 2**63 - 1


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorOut(BaseModel):
    detail: str


# --- Proveedores ---------------------------------------------------------------------------


class ProviderIn(Strict):
    name: str = Field(min_length=1, max_length=100, description="Nombre único del proveedor")
    url: str = Field(
        min_length=1,
        max_length=2048,
        description="URL HTTP(S) del inventario completo, sin credenciales embebidas",
    )

    @field_validator("url")
    @classmethod
    def http_without_credentials(cls, value):
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("La URL debe ser http o https")
        if parts.username or parts.password:
            raise ValueError("La URL no debe incluir credenciales")
        return value


class PreviewRow(BaseModel):
    sku: str
    stock: int


class Suggestion(BaseModel):
    item_id: str = Field(description="Publicación de la tienda")
    sku: str
    desired: int = Field(description="Cantidad según el proveedor")
    confirmed: int = Field(description="Cantidad actual en la tienda")


class StoreSuggestions(BaseModel):
    store: str
    total: int
    examples: list[Suggestion]


class ProviderCreated(BaseModel):
    id: int
    status: str
    sku: int = Field(description="SKU distintos válidos del inventario")
    parse_error_rate: float = Field(description="Fracción de filas descartadas por error")
    parse_alert: bool = Field(description="True si el error de parseo supera el 10 % (RF-14)")
    preview: list[PreviewRow] = Field(description="Muestra de la fuente")
    awaiting_first_ingest: bool
    next_run_at: datetime = Field(description="Próxima ingesta programada")
    suggestions: list[StoreSuggestions] = Field(
        description="Publicaciones sugeridas por tienda con catálogo importado"
    )


class ProviderOut(BaseModel):
    id: int
    name: str
    status: str
    active: bool
    next_run_at: datetime | None
    last_accepted_run: int | None
    last_error: str | None


class DisableOut(BaseModel):
    provider: int
    cuts: int = Field(description="Vínculos a los que se ordenó llevar a cero")


# --- Tiendas -------------------------------------------------------------------------------


class StoreIn(Strict):
    store: StoreId = Field(description="Identificador de la tienda en el marketplace")


class StoreOut(BaseModel):
    id: str
    status: str
    catalog_imported: bool
    processed: int = Field(description="Publicaciones importadas")
    total: int | None = Field(description="Total del catálogo; None hasta conocerlo")
    progress_percent: float
    last_error: str | None


# --- Vínculos ------------------------------------------------------------------------------


class SuggestionsOut(BaseModel):
    total: int
    items: list[Suggestion]


class ApproveIn(Strict):
    """Exactamente una selección: `all`, `items` o `count`."""

    store: StoreId
    all: bool = Field(False, description="Aprobar todas las sugerencias")
    items: list[Annotated[str, StringConstraints(min_length=1, max_length=64)]] | None = Field(
        None, min_length=1, max_length=10_000, description="Publicaciones concretas"
    )
    count: int | None = Field(None, ge=1, le=1_000_000, description="Las primeras N sugerencias")
    positive_only: bool = Field(False, description="Sólo publicaciones con stock mayor que cero")

    @model_validator(mode="after")
    def one_selection(self):
        chosen = [self.all, self.items is not None, self.count is not None]
        if sum(chosen) != 1:
            raise ValueError("Indicar exactamente una selección: all, items o count")
        return self


class ApproveOut(BaseModel):
    approved: int
    awaiting_ingest: bool = Field(description="True si el proveedor aún no tuvo su primera ingesta")


class LinkOut(BaseModel):
    id: int
    provider_id: int
    store_id: str
    item_id: str
    sku: str
    state: Literal["active", "error", "inactive"]
    cut_requested: bool
    desired: int
    confirmed: int
    initial_confirmed: int
    revision: int
    last_success_at: datetime | None
    last_error: str | None
    awaiting_ingest: bool
    pending: bool = Field(description="Hay una publicación pendiente en la cola")
    pending_quantity: int | None
    enqueued_at: datetime | None
    available_at: datetime | None
    replacements: int | None

    @field_validator("last_error")
    @classmethod
    def short_error(cls, value):
        return value[:500] if value else value


class LinksPage(BaseModel):
    items: list[LinkOut]
    next_offset: int | None = Field(description="Offset de la página siguiente; None en la última")


class LinkSummary(BaseModel):
    total: int
    awaiting_ingest: int
    pending: int
    failed: int
    synchronized: int
    inactive: int
    changed_from_initial: int
    positive_confirmed: int
    zero_confirmed: int


class LinkOffOut(BaseModel):
    link: int
    cuts: int


class LinkResumeOut(BaseModel):
    link: int
    status: str
