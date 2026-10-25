"""Descarga del feed. Acepta HTTP(S) y rutas locales (feeds generados y archivados)."""

from pathlib import Path

import httpx

TIMEOUT_SEGUNDOS = 120


def descargar(origen: str) -> bytes:
    """Devuelve el contenido crudo. Nunca loguea el origen: puede llevar credenciales."""
    if origen.startswith(("http://", "https://")):
        respuesta = httpx.get(origen, timeout=TIMEOUT_SEGUNDOS, follow_redirects=True)
        respuesta.raise_for_status()
        return respuesta.content
    ruta = Path(origen.removeprefix("file://"))
    return ruta.read_bytes()
