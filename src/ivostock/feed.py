"""Contrato de inventario y preparación con procedencia verificable."""

import hashlib
import json
from pathlib import Path

from ivostock.ingesta.coeficiente import calcular
from ivostock.ingesta.normalizacion import normalizar


def parse(raw):
    return normalizar(raw)


def suspicion(previous, current):
    score = calcular(previous, current)
    return {"D": score.D, "Z": score.Z, "p": score.p}


def changes(previous, current):
    return {
        sku: current.get(sku, 0)
        for sku in previous.keys() | current.keys()
        if previous.get(sku, 0) != current.get(sku, 0)
    }


def prepare(source: Path, directory: Path, provenance: str, captured_at: str):
    """El derivado conserva exactamente los bytes originales después de la cabecera."""
    raw = source.read_bytes()
    if raw.startswith(b"SKU;stock"):
        raise ValueError("La preparación requiere el original sin encabezado")
    derived = b"SKU;stock\n" + raw
    feed = parse(derived)
    original_hash = hashlib.sha256(raw).hexdigest()
    derived_hash = hashlib.sha256(derived).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{derived_hash}.csv"
    target.write_bytes(derived)
    manifest = {
        "provenance": provenance,
        "captured_at": captured_at,
        "original_sha256": original_hash,
        "derived_sha256": derived_hash,
        "original_bytes": len(raw),
        "derived_bytes": len(derived),
        "file": target.name,
        "rows": feed.lines,
        "distinct_sku": len(feed.stock),
        "parse_errors": sum(d["reason"] != "duplicate" for d in feed.discarded),
    }
    target.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
