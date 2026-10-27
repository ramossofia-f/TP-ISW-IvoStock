"""Importación de catálogo por la misma cuota y contrato del publicador."""

import time

import httpx

from ivostock.config import Settings
from ivostock.db import execute, execute_many, ownership, rows
from ivostock.failpoints import checkpoint
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


def register_store(engine, store):
    """Registra la tienda y deja su importación pendiente para el worker de catálogo."""
    with engine.begin() as conn:
        execute(conn, "INSERT INTO stores(id) VALUES (:s) ON CONFLICT DO NOTHING", s=store)
        return dict(rows(conn, "SELECT * FROM stores WHERE id=:s", s=store)[0])


def import_page(engine, store=None):
    """Importa una página; el avance se confirma junto con sus publicaciones."""
    with engine.begin() as conn:
        pending = rows(
            conn,
            "SELECT id FROM stores WHERE import_finished_at IS NULL AND blocked_until<=now() AND (CAST(:s AS text) IS NULL OR id=:s) ORDER BY id",
            s=store,
        )
    for candidate in pending:
        with ownership(engine, f"store:{candidate['id']}") as owner:
            if owner is not None:
                return _import_page(engine, owner, candidate["id"])
    return False


def _import_page(engine, owner, store):
    with owner.begin():
        current = rows(
            owner,
            "SELECT import_offset FROM stores WHERE id=:s AND import_finished_at IS NULL",
            s=store,
        )
    if not current:
        return False
    offset = current[0]["import_offset"]
    try:
        response = market_request(
            engine,
            store,
            "GET",
            f"/stores/{store}/items",
            params={"limit": 100, "offset": offset},
        )
        code = response.status_code
    except httpx.HTTPError as exc:
        response, code = None, 0
        error = type(exc).__name__
    if code == 200:
        page = response.json()
        with owner.begin():
            if page["items"]:
                execute_many(
                    owner,
                    "INSERT INTO catalog(store_id,item_id,sku,quantity) VALUES (:s,:i,:sku,:q) ON CONFLICT(store_id,item_id) DO NOTHING",
                    [
                        {"s": store, "i": i["id"], "sku": i["sku"], "q": i["available_quantity"]}
                        for i in page["items"]
                    ],
                )
            finished = page["next_offset"] is None
            execute(
                owner,
                "UPDATE stores SET import_offset=:o,import_total=:t,last_error=NULL,"
                "import_finished_at=CASE WHEN :f THEN now() END,"
                "status=CASE WHEN :f THEN 'healthy' ELSE status END WHERE id=:s",
                o=offset + len(page["items"]),
                t=page.get("total"),
                f=finished,
                s=store,
            )
        checkpoint("catalog_page_committed")
        return True
    if code == 429:
        delay, status, error = retry_delay(response), None, None
    elif code in (0, 401, 403):
        delay, status = 30, "degraded"
        error = f"HTTP {code} al importar" if code else error
    elif code >= 500:
        delay, status, error = 5, None, f"HTTP {code} al importar"
    else:
        with owner.begin():
            execute(
                owner,
                "UPDATE stores SET status='degraded',last_error=:e,blocked_until=now()+interval '5 minutes' WHERE id=:s",
                s=store,
                e=f"HTTP {code} al importar",
            )
        raise ValueError(f"Importación fallida: HTTP {code}")
    with owner.begin():
        execute(
            owner,
            "UPDATE stores SET blocked_until=now()+make_interval(secs=>:d),"
            "status=COALESCE(CAST(:st AS text),status),last_error=COALESCE(CAST(:e AS text),last_error)"
            " WHERE id=:s",
            d=delay,
            st=status,
            e=error,
            s=store,
        )
    return True


def add_store(engine, store):
    """Alta sincrónica: registra y completa la importación en este proceso."""
    register_store(engine, store)
    while True:
        with engine.begin() as conn:
            state = rows(conn, "SELECT * FROM stores WHERE id=:s", s=store)[0]
        if state["import_finished_at"] is not None:
            return {"store": store, "items": state["import_offset"]}
        if not import_page(engine, store):
            time.sleep(0.2)


def retry_delay(response):
    try:
        return max(1, min(3600, int(response.headers.get("Retry-After", "60"))))
    except ValueError:
        return 60
