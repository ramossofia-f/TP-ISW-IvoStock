"""Configuración y operación de proveedores, tiendas y vínculos."""

from ivostock.comparison import compare_once as compare_once
from ivostock.comparison import enqueue
from ivostock.db import execute, ownership, rows
from ivostock.failpoints import checkpoint
from ivostock.feed import parse
from ivostock.ingesta.fuente import descargar as fetch
from ivostock.ingesta.servicio import ingest as ingest
from ivostock.marketplace import add_store as add_store


def add_provider(engine, name, url):
    feed = parse(fetch(url))
    with engine.begin() as conn:
        provider = rows(
            conn,
            "INSERT INTO providers(name,url,status) VALUES (:n,:u,'validated') RETURNING id",
            n=name,
            u=url,
        )[0]
    return {"id": provider["id"], "preview": list(feed.stock.items())[:5]}


def suggestions(engine, provider, store, sku=None):
    with engine.begin() as conn:
        return rows(
            conn,
            "SELECT c.item_id,c.sku,s.quantity AS desired,c.quantity AS confirmed FROM catalog c JOIN stock s ON s.sku=c.sku AND s.provider_id=:p JOIN providers p ON p.id=:p JOIN stores t ON t.id=c.store_id WHERE c.store_id=:s AND p.active AND p.last_accepted_run IS NOT NULL AND t.status='healthy' AND (CAST(:sku AS text) IS NULL OR c.sku=:sku) AND NOT EXISTS (SELECT 1 FROM links l WHERE l.store_id=c.store_id AND l.item_id=c.item_id AND l.state!='inactive') ORDER BY c.item_id",
            p=provider,
            s=store,
            sku=sku,
        )


def approve(engine, provider, store, items=None):
    with ownership(engine, f"provider:{provider}") as owner:
        if owner is None:
            raise ValueError("Proveedor ocupado")
        options = suggestions(engine, provider, store)
        selected = [o for o in options if items is None or o["item_id"] in items]
        if items is not None and set(items) != {o["item_id"] for o in selected}:
            raise ValueError("Publicación no disponible para vincular")
        with owner.begin():
            for item in selected:
                execute(
                    owner,
                    "INSERT INTO links(provider_id,store_id,item_id,sku,desired,confirmed) VALUES (:p,:s,:i,:sku,:q,:c)",
                    p=provider,
                    s=store,
                    i=item["item_id"],
                    sku=item["sku"],
                    q=item["desired"],
                    c=item["confirmed"],
                )
            execute(owner, "INSERT INTO comparison_events(provider_id) VALUES (:p)", p=provider)
        return {"approved": len(selected)}


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


def status(engine, category="links"):
    queries = {
        "links": "SELECT l.*,t.enqueued_at,t.available_at,t.quantity AS pending_quantity,t.replacements FROM links l LEFT JOIN tasks t ON t.link_id=l.id ORDER BY l.id",
        "providers": "SELECT id,name,status,active,next_run_at,last_accepted_run,last_error FROM providers ORDER BY id",
        "stores": "SELECT * FROM stores ORDER BY id",
        "runs": "SELECT id,provider_id,status,snapshot_key,metrics,error,replay_of,started_at,finished_at FROM runs ORDER BY id",
        "quarantines": "SELECT * FROM runs WHERE status='quarantined' ORDER BY id",
        "deadletters": "SELECT * FROM dead_letters ORDER BY id",
        "tasks": "SELECT * FROM tasks ORDER BY enqueued_at,link_id",
    }
    with engine.begin() as conn:
        return [dict(r) for r in rows(conn, queries[category])]
