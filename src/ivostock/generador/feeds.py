"""Generador de feeds sintéticos (RF-37).

Produce feeds en formato `SKU<sep>stock` con los modos de falla que Celesa no genera a demanda:
truncado, ceros en masa, filas corruptas, deriva de stock, otro separador y encabezado.
La misma semilla y los mismos parámetros producen siempre el mismo archivo.

    python -m ivostock.generador.feeds --salida data/feeds/demo.csv --skus 5000
    python -m ivostock.generador.feeds --base data/feeds/demo.csv \
        --salida data/feeds/truncado.csv --truncar 0.3
"""

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from ivostock.ingesta.normalizacion import decodificar

STOCK_MAXIMO = 50  # rango observado en el feed real de Celesa (PRD §12)
VALORES_CORRUPTOS = ("abc", "-3", "N/D", "1,5")


@dataclass(frozen=True)
class Parametros:
    semilla: int = 42
    skus: int = 1000
    separador: str = ";"
    encabezado: bool = False
    truncar: float = 0.0
    ceros: float = 0.0
    corruptas: float = 0.0
    deriva: float = 0.0


def skus_sinteticos(cantidad: int, azar: random.Random) -> dict[str, int]:
    """ISBN-13 con prefijo 978 y algunos alfanuméricos, como en el feed real."""
    stock: dict[str, int] = {}
    while len(stock) < cantidad:
        sku = "978" + "".join(azar.choice("0123456789") for _ in range(10))
        if azar.random() < 0.001:
            sku = sku[:-3] + "X" + sku[-2:]
        stock[sku] = azar.randint(1, STOCK_MAXIMO)
    return stock


def leer_base(contenido: bytes, separador: str = ";") -> dict[str, int]:
    """Toma SKU y stock de un feed existente (por ejemplo un snapshot real, que no se versiona)."""
    texto, _ = decodificar(contenido)
    stock: dict[str, int] = {}
    for linea in texto.splitlines():
        campos = linea.split(separador)
        if len(campos) >= 2 and campos[0].strip() and campos[1].strip().isdigit():
            stock[campos[0].strip()] = int(campos[1].strip())
    return stock


def generar(parametros: Parametros, base: dict[str, int] | None = None) -> str:
    azar = random.Random(parametros.semilla)
    stock = dict(base) if base is not None else skus_sinteticos(parametros.skus, azar)
    skus = list(stock)

    for sku in azar.sample(skus, round(len(skus) * parametros.deriva)):
        stock[sku] = azar.randint(1, STOCK_MAXIMO)
    a_cero = set(azar.sample(skus, round(len(skus) * parametros.ceros)))
    corruptas = set(azar.sample(skus, round(len(skus) * parametros.corruptas)))

    sep = parametros.separador
    lineas = [f"sku{sep}stock"] if parametros.encabezado else []
    for sku in skus:
        if sku in corruptas:
            lineas.append(f"{sku}{sep}{azar.choice(VALORES_CORRUPTOS)}")
        elif sku in a_cero:
            # Cero explícito o en blanco: las dos formas valen 0 (RF-21).
            lineas.append(f"{sku}{sep}{azar.choice(('0', ''))}")
        else:
            lineas.append(f"{sku}{sep}{stock[sku]}")

    cuerpo = lineas[1:] if parametros.encabezado else lineas
    conservar = len(cuerpo) - round(len(cuerpo) * parametros.truncar)
    cuerpo = cuerpo[:conservar]
    lineas = (lineas[:1] if parametros.encabezado else []) + cuerpo
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ivostock.generador.feeds")
    parser.add_argument("--salida", required=True, type=Path)
    parser.add_argument("--base", type=Path, help="feed existente del que tomar SKU y stock")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--skus", type=int, default=1000)
    parser.add_argument("--separador", default=";")
    parser.add_argument("--encabezado", action="store_true")
    parser.add_argument("--truncar", type=float, default=0.0, help="fracción final que se corta")
    parser.add_argument("--ceros", type=float, default=0.0, help="fracción de SKU que pasan a 0")
    parser.add_argument(
        "--corruptas", type=float, default=0.0, help="fracción de filas con stock inválido"
    )
    parser.add_argument("--deriva", type=float, default=0.0, help="fracción de SKU con stock nuevo")
    args = parser.parse_args(argv)

    base = leer_base(args.base.read_bytes()) if args.base else None
    parametros = Parametros(
        semilla=args.semilla, skus=args.skus, separador=args.separador,
        encabezado=args.encabezado, truncar=args.truncar, ceros=args.ceros,
        corruptas=args.corruptas, deriva=args.deriva,
    )
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(generar(parametros, base), encoding="utf-8")
    print(f"Feed generado en {args.salida} con {parametros}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
