"""Configuración y operación de proveedores, tiendas y vínculos."""

from ivostock.comparison import compare_once as compare_once
from ivostock.comparison import enqueue
from ivostock.db import execute, execute_many, ownership, rows
from ivostock.failpoints import checkpoint
from ivostock.feed import parse
from ivostock.ingesta.fuente import descargar as fetch
from ivostock.ingesta.servicio import ingest as ingest
from ivostock.marketplace import add_store as add_store
from ivostock.marketplace import import_page as import_page
from ivostock.marketplace import register_store as register_store


def add_provider(engine, name, url):
    """Valida la fuente y guarda su vista previa; la primera ingesta queda a 300 minutos."""
    feed = parse(fetch(url))
    with engine.begin() as conn:
        provider = rows(
            conn,
            "INSERT INTO providers(name,url,status,next_run_at) VALUES (:n,:u,'validated',now()+interval '300 minutes') RETURNING id,next_run_at",
            n=name,
            u=url,
        )[0]
        with conn.connection.driver_connection.cursor().copy(
            "COPY provider_preview(provider_id,sku,quantity) FROM STDIN"
        ) as copy:
            for sku, quantity in feed.stock.items():
                copy.write_row((provider["id"], sku, quantity))
        stores = rows(
            conn, "SELECT id FROM stores WHERE import_finished_at IS NOT NULL ORDER BY id"
        )
    found = []
    for store in stores:
        options = suggestions(engine, provider["id"], store["id"])
        found.append({"store": store["id"], "total": len(options), "examples": options[:3]})
    return {
        "id": provider["id"],
        "status": "validated",
        "sku": len(feed.stock),
        "parse_error_rate": feed.error_rate,
        "preview": list(feed.stock.items())[:5],
        "awaiting_first_ingest": True,
        "next_run_at": provider["next_run_at"],
        "suggestions": found,
    }


def schedule_now(engine, provider):
    """Adelanta el vencimiento; la corrida sigue el circuito normal del worker."""
    with engine.begin() as conn:
        found = rows(
            conn,
            "UPDATE providers SET next_run_at=now() WHERE id=:p AND active RETURNING id,next_run_at",
            p=provider,
        )
    if not found:
        raise ValueError("Proveedor inexistente o inactivo")
    return dict(found[0])


def suggestions(engine, provider, store, sku=None, positive_only=False):
    """Coincidencias exactas contra la última corrida aceptada o, antes, la validación."""
    with engine.begin() as conn:
        accepted = rows(
            conn, "SELECT last_accepted_run FROM providers WHERE id=:p AND active", p=provider
        )
        if not accepted:
            return []
        source = "stock" if accepted[0]["last_accepted_run"] else "provider_preview"
        return [
            dict(r)
            for r in rows(
                conn,
                f"SELECT c.item_id,c.sku,s.quantity AS desired,c.quantity AS confirmed FROM catalog c JOIN {source} s ON s.sku=c.sku AND s.provider_id=:p JOIN stores t ON t.id=c.store_id WHERE c.store_id=:s AND t.import_finished_at IS NOT NULL AND (CAST(:sku AS text) IS NULL OR c.sku=:sku) AND (NOT :positive OR s.quantity>0) AND NOT EXISTS (SELECT 1 FROM links l WHERE l.store_id=c.store_id AND l.item_id=c.item_id AND l.state!='inactive') ORDER BY c.item_id",
                p=provider,
                s=store,
                sku=sku,
                positive=positive_only,
            )
        ]


def approve(engine, provider, store, items=None, count=None, positive_only=False):
    """Antes de la primera corrida aceptada los vínculos esperan sin generar trabajo."""
    with ownership(engine, f"provider:{provider}") as owner:
        if owner is None:
            raise ValueError("Proveedor ocupado")
        options = suggestions(engine, provider, store, positive_only=positive_only)
        selected = [o for o in options if items is None or o["item_id"] in items]
        if items is not None and set(items) != {o["item_id"] for o in selected}:
            raise ValueError("Publicación no disponible para vincular")
        if count is not None:
            if count < 1:
                raise ValueError("count debe ser positivo")
            selected = selected[:count]
        with owner.begin():
            ingested = rows(
                owner, "SELECT last_accepted_run FROM providers WHERE id=:p", p=provider
            )[0]["last_accepted_run"]
            if selected:
                execute_many(
                    owner,
                    "INSERT INTO links(provider_id,store_id,item_id,sku,desired,confirmed,initial_confirmed) VALUES (:p,:s,:i,:sku,:q,:c,:c)",
                    [
                        {
                            "p": provider,
                            "s": store,
                            "i": item["item_id"],
                            "sku": item["sku"],
                            "q": item["desired"] if ingested else item["confirmed"],
                            "c": item["confirmed"],
                        }
                        for item in selected
                    ],
                )
            if ingested:
                execute(owner, "INSERT INTO comparison_events(provider_id) VALUES (:p)", p=provider)
        return {"approved": len(selected), "awaiting_ingest": not ingested}


def cut(engine, provider, link_id=None):
    with ownership(engine, f"provider:{provider}") as conn:
        if conn is None:
            raise ValueError("Proveedor ocupado")
        with conn.begin():
            links = rows(
                conn,
                "SELECT * FROM links WHERE provider_id=:p AND state!='inactive' AND (CAST(:l AS bigint) IS NULL OR id=:l) FOR UPDATE",
                p=provider,
                l=link_id,
            )
            if link_id is not None and not links:
                raise ValueError("Vínculo inexistente o inactivo")
            if link_id is None:
                execute(
                    conn,
                    "UPDATE providers SET active=FALSE,status='disabled' WHERE id=:p",
                    p=provider,
                )
            for link in links:
                execute(conn, "UPDATE links SET cut_requested=TRUE WHERE id=:l", l=link["id"])
                link = dict(link, cut_requested=True)
                enqueue(conn, link, 0)
            checkpoint("cut_in_transaction")
        checkpoint("cut_committed")
    return {"cuts": len(links)}


def resume(engine, link_id):
    with engine.begin() as conn:
        found = rows(conn, "SELECT provider_id FROM links WHERE id=:l", l=link_id)
    if not found:
        raise ValueError("Vínculo inexistente")
    provider = found[0]["provider_id"]
    with ownership(engine, f"provider:{provider}") as conn:
        if conn is None:
            raise ValueError("Proveedor ocupado")
        with conn.begin():
            link = rows(
                conn,
                "SELECT l.*,COALESCE(s.quantity,0) AS source_quantity FROM links l LEFT JOIN stock s ON s.provider_id=l.provider_id AND s.sku=l.sku WHERE l.id=:l FOR UPDATE OF l",
                l=link_id,
            )[0]
            if link["state"] == "inactive":
                raise ValueError("Un vínculo inactivo se incorpora con la aprobación de vínculos")
            execute(
                conn,
                "UPDATE dead_letters SET reviewed_at=now() WHERE link_id=:l AND reviewed_at IS NULL",
                l=link_id,
            )
            execute(conn, "UPDATE links SET state='active',last_error=NULL WHERE id=:l", l=link_id)
            enqueue(
                conn,
                dict(link, state="active"),
                0 if link["cut_requested"] else link["source_quantity"],
            )
    return {"link": link_id, "status": "resumed"}


# Un vínculo espera la ingesta hasta que su proveedor tiene una corrida aceptada y comparada.
AWAITING = "(l.state!='inactive' AND t.link_id IS NULL AND (p.last_accepted_run IS NULL OR EXISTS (SELECT 1 FROM comparison_events e WHERE e.provider_id=l.provider_id AND e.processed_at IS NULL)))"

LINK_SUMMARY = f"""SELECT count(*) AS total,
 count(*) FILTER (WHERE {AWAITING}) AS awaiting_ingest,
 count(t.link_id) AS pending,
 count(*) FILTER (WHERE l.state='error') AS failed,
 count(*) FILTER (WHERE l.state='active' AND NOT {AWAITING} AND t.link_id IS NULL AND l.confirmed=l.desired) AS synchronized,
 count(*) FILTER (WHERE l.state='inactive') AS inactive,
 count(*) FILTER (WHERE l.confirmed!=l.initial_confirmed) AS changed_from_initial,
 count(*) FILTER (WHERE l.confirmed>0) AS positive_confirmed,
 count(*) FILTER (WHERE l.confirmed=0) AS zero_confirmed
 FROM links l JOIN providers p ON p.id=l.provider_id LEFT JOIN tasks t ON t.link_id=l.id
 WHERE CAST(:s AS text) IS NULL OR l.store_id=:s"""


def status(engine, category="links", store=None, summary=False, limit=None):
    queries = {
        "links": f"SELECT l.*,{AWAITING} AS awaiting_ingest,t.enqueued_at,t.available_at,t.quantity AS pending_quantity,t.replacements FROM links l JOIN providers p ON p.id=l.provider_id LEFT JOIN tasks t ON t.link_id=l.id WHERE CAST(:s AS text) IS NULL OR l.store_id=:s ORDER BY l.id LIMIT :n",
        "providers": "SELECT id,name,status,active,next_run_at,last_accepted_run,last_error FROM providers ORDER BY id",
        "stores": "SELECT id,status,last_error,blocked_until,import_offset AS processed,import_total AS total,import_finished_at FROM stores ORDER BY id",
        "runs": "SELECT id,provider_id,status,snapshot_key,metrics,error,replay_of,started_at,finished_at FROM runs ORDER BY id",
        "quarantines": "SELECT * FROM runs WHERE status='quarantined' ORDER BY id",
        "deadletters": "SELECT * FROM dead_letters ORDER BY id",
        "tasks": "SELECT * FROM tasks ORDER BY enqueued_at,link_id",
    }
    with engine.begin() as conn:
        if category == "links" and summary:
            return dict(rows(conn, LINK_SUMMARY, s=store)[0])
        found = [dict(r) for r in rows(conn, queries[category], s=store, n=limit)]
    if category == "links" and (store is not None or limit is not None):
        return {"items": found}
    return found


def monitor(engine, store=None, marketplace_calls=None):
    """Estado operativo de tiendas, importación, vínculos e intentos."""
    with engine.begin() as conn:
        stores = rows(
            conn,
            "SELECT s.id,s.status,s.last_error,s.blocked_until,s.import_offset,s.import_total,s.import_finished_at,(SELECT count(*) FROM market_calls m WHERE m.store_id=s.id AND m.at>clock_timestamp()-interval '60 seconds') AS client_calls_last_minute FROM stores s WHERE CAST(:s AS text) IS NULL OR s.id=:s ORDER BY s.id",
            s=store,
        )
        links = dict(rows(conn, LINK_SUMMARY, s=store)[0])
        attempts = rows(
            conn,
            "SELECT a.status,a.http_status,count(*) AS count FROM attempts a JOIN links l ON l.id=a.link_id WHERE CAST(:s AS text) IS NULL OR l.store_id=:s GROUP BY a.status,a.http_status ORDER BY a.status,a.http_status",
            s=store,
        )
        providers = rows(
            conn,
            "SELECT id,name,status,next_run_at,last_accepted_run,last_error FROM providers ORDER BY id",
        )
        now = rows(conn, "SELECT now() AS at")[0]["at"]
    return {
        "at": now,
        "stores": [
            {
                "id": s["id"],
                "status": "importing" if s["import_finished_at"] is None else s["status"],
                "last_error": s["last_error"],
                "client_calls_last_minute": s["client_calls_last_minute"],
                "marketplace_calls_last_minute": (
                    marketplace_calls(s["id"]) if marketplace_calls else None
                ),
            }
            for s in stores
        ],
        "catalogs": [
            {
                "store_id": s["id"],
                "status": "importing" if s["import_finished_at"] is None else "completed",
                "processed": s["import_offset"],
                "total": s["import_total"],
                "progress_percent": (
                    round(100 * s["import_offset"] / s["import_total"], 2)
                    if s["import_total"]
                    else 0.0
                ),
            }
            for s in stores
        ],
        "providers": [dict(p) for p in providers],
        "links": links,
        "attempts": [dict(a) for a in attempts],
    }
