"""Aprovisionamiento del marketplace simulado (ensayo).

En producción las tiendas ya existen: la aplicación sólo las registra (S-01). Aquí se crean en
el simulador con su API administrativa, que la aplicación nunca usa. Cada tienda recibe una
muestra del inventario del proveedor: un núcleo de SKU común a todas y el resto propio de cada
una, de modo que las muestras son distintas pero se solapan por construcción.
"""

import random
from pathlib import Path

import httpx

from ivostock.config import Settings
from ivostock.feed import parse

SEED = "ivostock-catalogo"


def store_samples(skus, stores, fraction=0.5, shared=0.5):
    """SKU de cada tienda: `fraction` del inventario, de los que `shared` son comunes.

    Es determinista: con las mismas entradas siempre da lo mismo. Las tiendas se reparten el
    resto en tramos consecutivos, así que agregar tiendas al final de `stores` no cambia las
    anteriores. Falla si no puede garantizar solapamiento y diferencias entre las tiendas.
    """
    if not 0 < fraction <= 1 or not 0 <= shared <= 1:
        raise ValueError("fraction debe estar entre 0 y 1, y shared entre 0 y 1")
    ordered = sorted(set(skus))
    random.Random(SEED).shuffle(ordered)
    size = int(len(ordered) * fraction)
    core = ordered[: int(size * shared)]
    own = size - len(core)
    rest = ordered[len(core) :]
    if len(stores) > 1 and (not core or not own):
        raise ValueError("El inventario es demasiado chico para muestras distintas y solapadas")
    if own * len(stores) > len(rest):
        raise ValueError("El inventario no alcanza para tantas tiendas con esa muestra")
    return {store: sorted(core + rest[n * own : (n + 1) * own]) for n, store in enumerate(stores)}


def catalog_items(skus):
    """Publicaciones de una tienda: un id propio por SKU y stock inicial en cero."""
    return [
        {"id": f"ITEM{n:06}", "sku": sku, "available_quantity": 0}
        for n, sku in enumerate(sorted(skus), 1)
    ]


def admin(method, path, payload=None):
    cfg = Settings.from_env()
    response = httpx.request(
        method,
        cfg.simulator_url + path,
        json=payload,
        headers={"Authorization": "Bearer " + cfg.simulator_admin_token},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def provision_stores(feed, stores, fraction=0.5, shared=0.5):
    """Crea en el simulador las tiendas que aún no existen. Es idempotente."""
    feed = Path(feed)
    if not feed.is_file():
        raise ValueError(f"No existe el inventario {feed} para preparar las tiendas")
    samples = store_samples(sorted(parse(feed.read_bytes()).stock), stores, fraction, shared)
    result = {}
    for store, skus in samples.items():
        if admin("GET", f"/admin/stores/{store}/summary")["exists"]:
            result[store] = {"status": "exists", "items": len(skus)}
            continue
        admin("POST", "/admin/seed", {"store": store, "items": catalog_items(skus)})
        result[store] = {"status": "created", "items": len(skus)}
    return result
