"""Feeds sintéticos reproducibles del contrato SKU;stock (ADR-0007)."""

import argparse
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from ivostock.ingesta.normalizacion import normalizar

STOCK_MAXIMO = 50
VALORES_CORRUPTOS = ("abc", "-3", "N/D", "1,5")


@dataclass(frozen=True)
class Parametros:
    semilla: int = 42
    skus: int = 1000
    truncar: float = 0.0
    ceros: float = 0.0
    corruptas: float = 0.0
    deriva: float = 0.0

    def __post_init__(self):
        if self.skus < 1:
            raise ValueError("skus debe ser positivo")
        for name in ("truncar", "ceros", "corruptas", "deriva"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} debe estar entre cero y uno")


def skus_sinteticos(cantidad: int, azar: random.Random) -> dict[str, int]:
    stock = {}
    while len(stock) < cantidad:
        sku = "978" + "".join(azar.choice("0123456789") for _ in range(10))
        if azar.random() < 0.001:
            sku = sku[:-3] + "X" + sku[-2:]
        stock[sku] = azar.randint(1, STOCK_MAXIMO)
    return stock


def leer_base(contenido: bytes) -> dict[str, int]:
    result = normalizar(contenido)
    if result.error_rate:
        raise ValueError("La base del generador no debe tener errores de parseo")
    return result.stock


def generar(parametros: Parametros, base: dict[str, int] | None = None) -> str:
    azar = random.Random(parametros.semilla)
    stock = dict(base) if base is not None else skus_sinteticos(parametros.skus, azar)
    skus = sorted(stock)
    for sku in azar.sample(skus, round(len(skus) * parametros.deriva)):
        stock[sku] = azar.choice(
            [quantity for quantity in range(1, STOCK_MAXIMO + 1) if quantity != stock[sku]]
        )
    a_cero = set(azar.sample(skus, round(len(skus) * parametros.ceros)))
    corruptas = set(azar.sample(skus, round(len(skus) * parametros.corruptas)))
    cuerpo = []
    for sku in skus:
        if sku in corruptas:
            quantity = azar.choice(VALORES_CORRUPTOS)
        elif sku in a_cero:
            quantity = azar.choice(("0", ""))
        else:
            quantity = str(stock[sku])
        cuerpo.append(f"{sku};{quantity}")
    conservar = len(cuerpo) - round(len(cuerpo) * parametros.truncar)
    return "SKU;stock\n" + "".join(line + "\n" for line in cuerpo[:conservar])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", required=True, type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--skus", type=int, default=1000)
    for name in ("truncar", "ceros", "corruptas", "deriva"):
        parser.add_argument("--" + name, type=float, default=0)
    args = parser.parse_args(argv)
    parametros = Parametros(
        **{name: getattr(args, name) for name in Parametros.__dataclass_fields__}
    )
    base = leer_base(args.base.read_bytes()) if args.base else None
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    content = generar(parametros, base).encode("utf-8")
    args.salida.write_bytes(content)
    metadata = {
        "synthetic": True,
        "parameters": asdict(parametros),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    if args.base:
        metadata["base_sha256"] = hashlib.sha256(args.base.read_bytes()).hexdigest()
    args.salida.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Escenario sintético generado en {args.salida}: {parametros}")


if __name__ == "__main__":
    main()
