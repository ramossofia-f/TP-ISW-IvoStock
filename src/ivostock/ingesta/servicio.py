"""Aceptación transaccional de inventarios HTTP y cuarentena."""

import hashlib
import json
import logging

import httpx
from botocore.exceptions import BotoCoreError, ClientError

from ivostock.db import execute, ownership, rows
from ivostock.failpoints import checkpoint
from ivostock.feed import parse, suspicion
from ivostock.ingesta.fuente import descargar as fetch
from ivostock.storage import Snapshots

log = logging.getLogger("ivostock.ingesta")


def json_value(value):
    return json.dumps(value, ensure_ascii=False)


def ingest(engine, provider_id, replay_of=None, scheduled=False):
    with ownership(engine, f"provider:{provider_id}") as conn:
        if conn is None:
            return {"status": "busy"}
        with conn.begin():
            providers = rows(conn, "SELECT * FROM providers WHERE id=:p AND active", p=provider_id)
            if not providers:
                raise ValueError("Proveedor inexistente o inactivo")
            provider = providers[0]
            if scheduled:
                due = rows(
                    conn,
                    "SELECT next_run_at <= now() AS due FROM providers WHERE id=:p",
                    p=provider_id,
                )[0]["due"]
                abandoned = rows(
                    conn,
                    "SELECT 1 FROM runs WHERE provider_id=:p AND status='running' LIMIT 1",
                    p=provider_id,
                )
                if not due and not abandoned:
                    return {"status": "not_due"}
                if due:
                    execute(
                        conn,
                        "UPDATE providers SET next_run_at=now()+interval '300 minutes' WHERE id=:p",
                        p=provider_id,
                    )
            execute(
                conn,
                "UPDATE runs SET status='interrupted',finished_at=now(),error='Proceso interrumpido' WHERE provider_id=:p AND status='running'",
                p=provider_id,
            )
            run_id = rows(
                conn,
                "INSERT INTO runs(provider_id,replay_of) VALUES (:p,:r) RETURNING id",
                p=provider_id,
                r=replay_of,
            )[0]["id"]
        try:
            snapshots = Snapshots()
            if replay_of is not None:
                with conn.begin():
                    original = rows(
                        conn,
                        "SELECT snapshot_key FROM runs WHERE id=:r AND provider_id=:p",
                        r=replay_of,
                        p=provider_id,
                    )
                if not original or not original[0]["snapshot_key"]:
                    raise ValueError("La corrida no tiene snapshot reproducible de este proveedor")
                raw = snapshots.get(original[0]["snapshot_key"])
            else:
                raw = fetch(provider["url"])
            key = snapshots.put(raw)
            with conn.begin():
                execute(conn, "UPDATE runs SET snapshot_key=:k WHERE id=:r", k=key, r=run_id)
            checkpoint("snapshot_stored")
            feed = parse(raw)
            with conn.begin():
                last = rows(
                    conn,
                    "SELECT snapshot_key FROM runs WHERE id=:r",
                    r=provider["last_accepted_run"],
                )
                same_snapshot = bool(last and last[0]["snapshot_key"] == key)
                previous = (
                    {}
                    if same_snapshot
                    else {
                        r["sku"]: r["quantity"]
                        for r in rows(
                            conn,
                            "SELECT sku,quantity FROM stock WHERE provider_id=:p",
                            p=provider_id,
                        )
                    }
                )
                score = (
                    suspicion(previous, feed.stock)
                    if provider["last_accepted_run"] and not same_snapshot
                    else {"D": 0, "Z": 0, "p": 0}
                )
                metrics = {
                    **score,
                    "rows": feed.lines,
                    "sku": len(feed.stock),
                    "discarded": feed.discarded,
                    "parse_error_rate": feed.error_rate,
                    "parse_alert": feed.error_rate > 0.10,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "reused_inventory": same_snapshot,
                }
                trace = {"component": "ingest", "run": run_id, "provider": provider_id}
                if metrics["parse_alert"]:
                    log.warning("Más del 10 por ciento de filas con error de parseo", extra=trace)
                if score["p"] > 0.5:
                    log.warning("Corrida en cuarentena", extra={**trace, "status": "quarantined"})
                    execute(
                        conn,
                        "UPDATE runs SET status='quarantined',metrics=CAST(:m AS jsonb),finished_at=now() WHERE id=:r",
                        m=json_value(metrics),
                        r=run_id,
                    )
                    execute(
                        conn,
                        "UPDATE providers SET status='degraded',last_error='Corrida en cuarentena' WHERE id=:p",
                        p=provider_id,
                    )
                    return {"id": run_id, "status": "quarantined", "p": score["p"]}
                if not same_snapshot:
                    _replace_inventory(conn, provider_id, feed.stock)
                checkpoint("state_in_transaction")
                execute(
                    conn,
                    "UPDATE runs SET status='accepted',metrics=CAST(:m AS jsonb),finished_at=now() WHERE id=:r",
                    m=json_value(metrics),
                    r=run_id,
                )
                execute(
                    conn,
                    "UPDATE providers SET status='healthy',last_error=NULL,last_accepted_run=:r WHERE id=:p",
                    r=run_id,
                    p=provider_id,
                )
                execute(
                    conn,
                    "INSERT INTO comparison_events(provider_id,run_id) VALUES (:p,:r)",
                    p=provider_id,
                    r=run_id,
                )
            checkpoint("accepted_committed")
            log.info("Corrida aceptada", extra={**trace, "status": "accepted"})
            return {"id": run_id, "status": "accepted", "sku": len(feed.stock)}
        except (httpx.HTTPError, ValueError, UnicodeError, BotoCoreError, ClientError) as exc:
            # El mensaje de una excepción HTTP puede incluir credenciales en la URL.
            error = type(exc).__name__
            log.error(
                "Corrida fallida",
                extra={
                    "component": "ingest",
                    "run": run_id,
                    "provider": provider_id,
                    "status": "failed",
                    "error": error,
                },
            )
            with conn.begin():
                execute(
                    conn,
                    "UPDATE runs SET status='failed',error=:e,finished_at=now() WHERE id=:r",
                    e=error,
                    r=run_id,
                )
                execute(
                    conn,
                    "UPDATE providers SET status='degraded',last_error=:e WHERE id=:p",
                    e=error,
                    p=provider_id,
                )
            return {"id": run_id, "status": "failed", "error": error}


def _replace_inventory(conn, provider_id, stock):
    execute(
        conn,
        "CREATE TEMP TABLE incoming_stock(sku TEXT PRIMARY KEY,quantity INTEGER) ON COMMIT DROP",
    )
    with conn.connection.driver_connection.cursor().copy(
        "COPY incoming_stock(sku,quantity) FROM STDIN"
    ) as copy:
        for item in stock.items():
            copy.write_row(item)
    execute(conn, "ANALYZE incoming_stock")
    execute(
        conn,
        "DELETE FROM stock s WHERE provider_id=:p AND NOT EXISTS (SELECT 1 FROM incoming_stock n WHERE n.sku=s.sku)",
        p=provider_id,
    )
    execute(
        conn,
        "INSERT INTO stock(provider_id,sku,quantity) SELECT :p,sku,quantity FROM incoming_stock ON CONFLICT(provider_id,sku) DO UPDATE SET quantity=EXCLUDED.quantity WHERE stock.quantity IS DISTINCT FROM EXCLUDED.quantity",
        p=provider_id,
    )
