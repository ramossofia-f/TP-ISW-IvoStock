"""Proveedor HTTP de ensayo: sirve inventarios archivados con variantes sintéticas.

En cada consulta selecciona el 40 % de las filas y permuta entre ellas sus
cantidades positivas. Los ceros, el orden de los SKU y el archivo base no cambian.
Con `?no-changes=true` devuelve los bytes archivados sin modificar.
"""

import os
import random
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

app = FastAPI(title="Proveedor de ensayo", version="0.1.0")
NAME = re.compile(r"^[A-Za-z0-9_-]+\.csv$")


def variar(raw: bytes, rng: random.Random, fraccion: float = 0.4) -> bytes:
    lines = raw.decode("utf-8").split("\n")
    candidates = []
    for index, line in enumerate(lines[1:], 1):
        fields = line.split(";")
        if len(fields) == 2 and fields[1].strip().isdigit() and int(fields[1]) > 0:
            candidates.append(index)
    data_rows = sum(1 for line in lines[1:] if line.strip())
    selected = rng.sample(candidates, min(len(candidates), round(data_rows * fraccion)))
    quantities = [lines[i].split(";")[1] for i in selected]
    rng.shuffle(quantities)
    for index, quantity in zip(selected, quantities, strict=True):
        lines[index] = lines[index].split(";")[0] + ";" + quantity
    return "\n".join(lines).encode("utf-8")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/{name}")
def feed(name: str, no_changes: bool = Query(False, alias="no-changes")):
    path = Path(os.getenv("FEEDS_DIR", "/feeds")) / name
    if not NAME.match(name) or not path.is_file():
        raise HTTPException(404, "Inventario inexistente")
    raw = path.read_bytes()
    body = raw if no_changes else variar(raw, random.Random())
    return Response(body, media_type="text/csv; charset=utf-8")
