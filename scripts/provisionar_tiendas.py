"""Crea en el simulador las tiendas del marketplace (ensayo; en producción ya existirían).

Uso: docker compose run --rm cli python scripts/provisionar_tiendas.py

Lee el inventario de CATALOG_FEED y las tiendas de MARKETPLACE_STORES. Cada tienda recibe la
mitad de los SKU, con la mitad de ellos comunes a todas. Se puede repetir sin efecto.
"""

import argparse
import json
import os
import sys

from ivostock.config import parse_stores
from ivostock.provision import provision_stores


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--feed", default=os.getenv("CATALOG_FEED", "data/feeds/celesa.csv"))
    ap.add_argument("--stores", default=os.getenv("MARKETPLACE_STORES", "T1,T2"))
    ap.add_argument("--sample", type=float, default=0.5, help="fracción del inventario por tienda")
    ap.add_argument("--shared", type=float, default=0.5, help="fracción de la muestra común")
    args = ap.parse_args()
    try:
        result = provision_stores(args.feed, parse_stores(args.stores), args.sample, args.shared)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
