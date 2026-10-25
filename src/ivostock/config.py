"""Configuración por entorno. Nada de credenciales en el código (RNF-07)."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def cargar_env(ruta: Path | None = None) -> None:
    """Carga un archivo .env simple sin pisar variables ya definidas en el entorno."""
    ruta = ruta or RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


def requerida(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno {nombre} (ver .env.example)")
    return valor
