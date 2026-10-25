"""Importación de catálogo por la misma cuota y contrato del publicador."""

import time

import httpx

from ivostock.config import Settings
from ivostock.db import execute, ownership
from ivostock.quota import reserve


def market_request(engine, store, method, path, **kwargs):
    cfg = Settings.from_env()
    while wait := reserve(engine, store):
        time.sleep(min(wait, 1))
    with httpx.Client(timeout=10) as client:
        return client.request(
            method,
            cfg.simulator_url + path,
            headers={"Authorization": f"Bearer {cfg.simulator_token}"},
            **kwargs,
        )


def add_store(engine, store):
    with ownership(engine, f"store:{store}") as owner:
        if owner is None:
            raise ValueError("Tienda ocupada; reintentá")
        with owner.begin():
            execute(owner, "INSERT INTO stores(id) VALUES (:s) ON CONFLICT DO NOTHING", s=store)
        cursor = ""
        count = 0
        while True:
            response = market_request(
                engine,
                store,
                "GET",
                f"/stores/{store}/items",
                params={"cursor": cursor, "limit": 100},
            )
            if response.status_code == 429:
                time.sleep(retry_delay(response))
                continue
            if response.status_code != 200:
                with owner.begin():
                    execute(
                        owner,
                        "UPDATE stores SET status='degraded',last_error=:e WHERE id=:s",
                        s=store,
                        e=f"HTTP {response.status_code} al importar",
                    )
                raise ValueError(f"Importación fallida: HTTP {response.status_code}")
            page = response.json()
            with owner.begin():
                for item in page["items"]:
                    execute(
                        owner,
                        "INSERT INTO catalog(store_id,item_id,sku,quantity) VALUES (:s,:i,:sku,:q) ON CONFLICT(store_id,item_id) DO NOTHING",
                        s=store,
                        i=item["id"],
                        sku=item["sku"],
                        q=item["available_quantity"],
                    )
            count += len(page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        with owner.begin():
            execute(
                owner, "UPDATE stores SET status='healthy',last_error=NULL WHERE id=:s", s=store
            )
        return {"store": store, "items": count}


def retry_delay(response):
    try:
        return max(1, min(3600, int(response.headers.get("Retry-After", "60"))))
    except ValueError:
        return 60
