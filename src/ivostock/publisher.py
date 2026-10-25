import json
import math

import httpx

from ivostock.config import Settings
from ivostock.db import execute, ownership, rows
from ivostock.failpoints import checkpoint
from ivostock.marketplace import retry_delay
from ivostock.quota import reserve


def publish_once(engine):
    with engine.begin() as conn:
        stores = rows(
            conn,
            "SELECT DISTINCT l.store_id FROM tasks t JOIN links l ON l.id=t.link_id JOIN stores s ON s.id=l.store_id WHERE l.state='active' AND t.available_at<=now() AND (t.claimed_until IS NULL OR t.claimed_until<now()) AND s.blocked_until<=now() ORDER BY l.store_id",
        )
    for store in stores:
        with ownership(engine, f"store:{store['store_id']}") as conn:
            if conn is not None and publish_store(engine, conn, store["store_id"]):
                return True
    return False


def publish_store(engine, conn, store):
    cfg = Settings.from_env()
    with conn.begin():
        tasks = rows(
            conn,
            "SELECT t.*,l.item_id FROM tasks t JOIN links l ON l.id=t.link_id WHERE l.store_id=:s AND l.state='active' AND t.available_at<=now() AND (t.claimed_until IS NULL OR t.claimed_until<now()) ORDER BY t.enqueued_at,t.link_id LIMIT 1 FOR UPDATE OF t SKIP LOCKED",
            s=store,
        )
        if not tasks:
            return False
        task = tasks[0]
    wait = reserve(engine, store)
    if wait:
        with conn.begin():
            execute(
                conn,
                "UPDATE stores SET blocked_until=clock_timestamp()+make_interval(secs=>:w) WHERE id=:s",
                w=wait,
                s=store,
            )
        return False
    # La cuota se reserva antes del claim: las caídas pueden desperdiciar permiso, nunca crearlo.
    with conn.begin():
        current = rows(
            conn,
            "SELECT t.*,l.item_id FROM tasks t JOIN links l ON l.id=t.link_id WHERE link_id=:l AND l.state='active' FOR UPDATE OF t",
            l=task["link_id"],
        )
        if not current:
            return False
        task = current[0]
        execute(
            conn,
            "UPDATE attempts SET status='interrupted',finished_at=now() WHERE link_id=:l AND status='in_flight'",
            l=task["link_id"],
        )
        attempt = rows(
            conn,
            "INSERT INTO attempts(link_id,revision,quantity,run_id) VALUES (:l,:r,:q,:run) RETURNING id",
            l=task["link_id"],
            r=task["revision"],
            q=task["quantity"],
            run=task["run_id"],
        )[0]["id"]
        execute(
            conn,
            "UPDATE tasks SET claimed_revision=revision,claimed_until=now()+make_interval(secs=>:lease) WHERE link_id=:l",
            lease=cfg.lease_seconds,
            l=task["link_id"],
        )
    checkpoint("task_claimed")
    try:
        with httpx.Client(timeout=10) as client:
            response = client.put(
                f"{cfg.simulator_url}/stores/{store}/items/{task['item_id']}/stock",
                headers={"Authorization": f"Bearer {cfg.simulator_token}"},
                json={"available_quantity": task["quantity"]},
            )
        code = response.status_code
        body = response.text[:2000]
    except httpx.HTTPError as exc:
        response, code, body = None, 0, type(exc).__name__
    checkpoint("marketplace_responded")
    with conn.begin():
        link = rows(conn, "SELECT * FROM links WHERE id=:l FOR UPDATE", l=task["link_id"])[0]
        latest = rows(conn, "SELECT * FROM tasks WHERE link_id=:l FOR UPDATE", l=task["link_id"])[0]
        same = latest["revision"] == task["revision"]
        params = {"l": link["id"], "a": attempt, "code": code, "body": body}
        execute(
            conn,
            "UPDATE attempts SET http_status=:code,response=:body,finished_at=now() WHERE id=:a",
            **params,
        )
        if code == 200:
            execute(
                conn,
                "UPDATE links SET confirmed=:q,last_success_at=now(),last_error=NULL WHERE id=:l",
                q=task["quantity"],
                l=link["id"],
            )
            execute(
                conn,
                "UPDATE catalog SET quantity=:q WHERE store_id=:s AND item_id=:i",
                q=task["quantity"],
                s=store,
                i=link["item_id"],
            )
            execute(conn, "UPDATE stores SET status='healthy',last_error=NULL WHERE id=:s", s=store)
            execute(conn, "UPDATE attempts SET status='applied' WHERE id=:a", a=attempt)
            if same:
                execute(conn, "DELETE FROM tasks WHERE link_id=:l", l=link["id"])
                if link["cut_requested"] and task["quantity"] == 0:
                    execute(conn, "UPDATE links SET state='inactive' WHERE id=:l", l=link["id"])
            else:
                execute(
                    conn,
                    "UPDATE tasks SET claimed_until=NULL,claimed_revision=NULL,available_at=now() WHERE link_id=:l",
                    l=link["id"],
                )
        elif code == 429:
            delay = retry_delay(response)
            execute(conn, "UPDATE attempts SET status='rate_limited' WHERE id=:a", a=attempt)
            execute(
                conn,
                "UPDATE stores SET blocked_until=now()+make_interval(secs=>:d) WHERE id=:s",
                d=delay,
                s=store,
            )
            execute(
                conn,
                "UPDATE tasks SET claimed_until=NULL,claimed_revision=NULL WHERE link_id=:l",
                l=link["id"],
            )
        elif code in (0, 401, 403):
            execute(conn, "UPDATE attempts SET status='store_unavailable' WHERE id=:a", a=attempt)
            execute(
                conn,
                "UPDATE stores SET status='degraded',last_error=:e,blocked_until=now()+interval '30 seconds' WHERE id=:s",
                s=store,
                e=f"HTTP {code}" if code else body,
            )
            execute(
                conn,
                "UPDATE tasks SET claimed_until=NULL,claimed_revision=NULL WHERE link_id=:l",
                l=link["id"],
            )
        elif not same:
            execute(conn, "UPDATE attempts SET status='superseded' WHERE id=:a", a=attempt)
            execute(
                conn,
                "UPDATE tasks SET claimed_until=NULL,claimed_revision=NULL WHERE link_id=:l",
                l=link["id"],
            )
        elif code >= 500 and latest["attempts"] < 4:
            delay = 5 * math.pow(2, latest["attempts"])
            execute(conn, "UPDATE attempts SET status='retry' WHERE id=:a", a=attempt)
            execute(
                conn,
                "UPDATE tasks SET attempts=attempts+1,claimed_until=NULL,claimed_revision=NULL,available_at=now()+make_interval(secs=>:d) WHERE link_id=:l",
                d=delay,
                l=link["id"],
            )
        else:
            execute(conn, "UPDATE attempts SET status='dead_letter' WHERE id=:a", a=attempt)
            execute(
                conn,
                "INSERT INTO dead_letters(link_id,attempt_id,revision,quantity,http_status,response) VALUES (:l,:a,:r,:q,:code,:body)",
                r=task["revision"],
                q=task["quantity"],
                **params,
            )
            execute(conn, "UPDATE links SET state='error',last_error=:body WHERE id=:l", **params)
            execute(conn, "DELETE FROM tasks WHERE link_id=:l", l=link["id"])
        checkpoint("ack_in_transaction")
    checkpoint("ack_committed")
    print(
        json.dumps(
            {
                "component": "publish",
                "store": store,
                "link": task["link_id"],
                "run": task["run_id"],
                "revision": task["revision"],
                "attempt": attempt,
                "http_status": code,
            }
        ),
        flush=True,
    )
    return True
