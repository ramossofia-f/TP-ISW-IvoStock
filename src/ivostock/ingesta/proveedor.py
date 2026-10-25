"""Configuración de un proveedor con formato .csv (RF-04, RF-08)."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ivostock.config import RAIZ

PRIORIDADES = ("baja", "media", "alta")
DIRECTORIO = RAIZ / "config" / "proveedores"


@dataclass(frozen=True)
class ConfigProveedor:
    """Separador, encabezado y posición (o nombre, con encabezado) de las columnas de SKU y stock.

    La URL se toma de una variable de entorno (`url_env`) cuando lleva credenciales,
    o directamente de `url` para archivos locales y feeds generados.
    """

    id: str
    separador: str
    encabezado: bool
    col_sku: int | str
    col_stock: int | str
    prioridad: str = "media"
    url_env: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if self.prioridad not in PRIORIDADES:
            raise ValueError(f"Prioridad inválida: {self.prioridad}")
        por_nombre = isinstance(self.col_sku, str) or isinstance(self.col_stock, str)
        if not self.encabezado and por_nombre:
            raise ValueError("Sin encabezado, las columnas se indican por posición")
        if bool(self.url_env) == bool(self.url):
            raise ValueError("Indicar url_env o url, no ambas")

    def origen(self) -> str:
        if self.url:
            return self.url
        valor = os.environ.get(self.url_env or "")
        if not valor:
            raise RuntimeError(f"Falta la variable de entorno {self.url_env} con la URL del feed")
        return valor

    def como_dict(self) -> dict:
        return asdict(self)


def cargar(proveedor_id: str, directorio: Path = DIRECTORIO) -> ConfigProveedor:
    ruta = directorio / f"{proveedor_id}.json"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la configuración del proveedor: {ruta}")
    return ConfigProveedor(**json.loads(ruta.read_text(encoding="utf-8")))
