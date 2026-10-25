"""Línea de comandos de la ingesta. El POC no tiene interfaz gráfica.

    python -m ivostock.ingesta init-db
    python -m ivostock.ingesta probar --proveedor celesa     # preview y fetch de prueba
    python -m ivostock.ingesta correr --proveedor celesa     # una corrida (RF-20 a RF-22, RF-28)
    python -m ivostock.ingesta corridas --proveedor celesa   # últimas corridas y cuarentenas
"""

import argparse
import sys
from datetime import UTC, datetime

from ivostock import config, logs
from ivostock.ingesta import fuente, proveedor
from ivostock.ingesta.normalizacion import normalizar
from ivostock.ingesta.repositorio import RepositorioPostgres
from ivostock.ingesta.servicio import ejecutar_corrida
from ivostock.ingesta.snapshots import AlmacenS3

MINIMO_FILAS_VALIDAS = 5


def _repositorio() -> RepositorioPostgres:
    return RepositorioPostgres(config.requerida("DATABASE_URL"))


def init_db(_: argparse.Namespace) -> int:
    repositorio = _repositorio()
    repositorio.crear_esquema()
    repositorio.cerrar()
    print("Esquema de la base del motor creado")
    return 0


def probar(args: argparse.Namespace) -> int:
    cfg = proveedor.cargar(args.proveedor)
    normalizada = normalizar(fuente.descargar(cfg.origen()), cfg)
    print(
        f"Filas: {normalizada.filas:,}  SKU válidos: {len(normalizada.stock):,}  "
        f"errores de parseo: {normalizada.errores_parseo:,}  "
        f"duplicados: {normalizada.duplicados:,}  encoding: {normalizada.encoding}"
    )
    print("\nPrimeras filas parseadas (SKU -> stock):")
    for sku, stock in list(normalizada.stock.items())[: args.filas]:
        print(f"  {sku:<20} {stock}")
    if len(normalizada.stock) < MINIMO_FILAS_VALIDAS:
        print(f"\nNo validado: hacen falta al menos {MINIMO_FILAS_VALIDAS} filas válidas")
        return 1
    repositorio = _repositorio()
    repositorio.registrar_proveedor(cfg, datetime.now(UTC))
    repositorio.cerrar()
    print(f"\nProveedor '{cfg.id}' validado")
    return 0


def correr(args: argparse.Namespace) -> int:
    cfg = proveedor.cargar(args.proveedor)
    repositorio = _repositorio()
    if not repositorio.proveedor_validado(cfg.id):
        print(f"El proveedor '{cfg.id}' no está validado: correr primero `probar`")
        return 1
    corrida = ejecutar_corrida(
        cfg, descargar=fuente.descargar, almacen=AlmacenS3(), repositorio=repositorio
    )
    repositorio.cerrar()
    detalle = f" ({corrida.motivo})" if corrida.motivo else ""
    print(f"Corrida {corrida.id}: {corrida.estado}{detalle}")
    return 0 if corrida.estado != "fallida" else 1


def corridas(args: argparse.Namespace) -> int:
    repositorio = _repositorio()
    filas = repositorio.ultimas_corridas(args.proveedor, args.limite)
    repositorio.cerrar()
    print(f"{'iniciada':<20} {'estado':<11} {'filas':>8} {'D':>8} {'Z':>8} {'p':>6}  motivo")
    for c in filas:
        def fmt(valor: float | None) -> str:
            return "" if valor is None else f"{valor:.4f}"

        print(f"{c.iniciada:%Y-%m-%d %H:%M:%S}  {c.estado:<11} {c.filas:>8,} {fmt(c.senal_d):>8} "
              f"{fmt(c.senal_z):>8} {fmt(c.coeficiente):>6}  {c.motivo or ''}")
    return 0


def main(argv: list[str] | None = None) -> int:
    config.cargar_env()
    logs.configurar()
    parser = argparse.ArgumentParser(prog="python -m ivostock.ingesta")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("init-db").set_defaults(func=init_db)
    p = sub.add_parser("probar")
    p.add_argument("--proveedor", required=True)
    p.add_argument("--filas", type=int, default=10)
    p.set_defaults(func=probar)
    c = sub.add_parser("correr")
    c.add_argument("--proveedor", required=True)
    c.set_defaults(func=correr)
    lst = sub.add_parser("corridas")
    lst.add_argument("--proveedor", required=True)
    lst.add_argument("--limite", type=int, default=20)
    lst.set_defaults(func=corridas)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
