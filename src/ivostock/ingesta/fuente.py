"""Descarga de proveedores por HTTP, sin revelar la URL en registros."""

from urllib.parse import urlsplit

import httpx


def descargar(url: str) -> bytes:
    if urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("El proveedor requiere una URL HTTP")
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content
