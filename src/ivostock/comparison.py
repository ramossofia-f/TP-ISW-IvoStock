"""Comparación por vínculo y cola durable con reemplazo de revisión."""

from ivostock.db import execute, ownership, rows
from ivostock.failpoints import checkpoint


def enqueue(conn, link, desired):
    revision = link["revision"] + (desired != link["desired"])
    execute(
        conn,
        "UPDATE links SET desired=:q,revision=:r WHERE id=:l",
        q=desired,
        r=revision,
        l=link["id"],
    )
    task = rows(conn, "SELECT * FROM tasks WHERE link_id=:l", l=link["id"])
    if link["state"] != "active":
        return
    if desired == link["confirmed"] and not task and not link["cut_requested"]:
        return
    if task and task[0]["quantity"] == desired and task[0]["revision"] == revision:
        return
    execute(
        conn,
        """INSERT INTO tasks(link_id,revision,quantity,run_id) VALUES (:l,:r,:q,:run)
        ON CONFLICT(link_id) DO UPDATE SET revision=EXCLUDED.revision,quantity=EXCLUDED.quantity,
        run_id=EXCLUDED.run_id, attempts=0, available_at=now(), replacements=tasks.replacements+1""",
        l=link["id"],
        r=revision,
        q=desired,
        run=link.get("run_id"),
    )


def compare_once(engine):
    with engine.begin() as conn:
        pending = rows(
            conn,
            "SELECT provider_id FROM comparison_events WHERE processed_at IS NULL GROUP BY provider_id ORDER BY min(id) LIMIT 100",
        )
    return any(_compare_provider(engine, p["provider_id"]) for p in pending)


def _compare_provider(engine, provider):
    with ownership(engine, f"provider:{provider}") as conn:
        if conn is None:
            return False
        with conn.begin():
            events = rows(
                conn,
                "SELECT id FROM comparison_events WHERE provider_id=:p AND processed_at IS NULL FOR UPDATE",
                p=provider,
            )
            if not events:
                return False
            checkpoint("comparison_claimed")
            run_id = rows(conn, "SELECT last_accepted_run FROM providers WHERE id=:p", p=provider)[
                0
            ]["last_accepted_run"]
            links = rows(
                conn,
                "SELECT l.*,COALESCE(s.quantity,0) AS source_quantity FROM links l LEFT JOIN stock s ON s.provider_id=l.provider_id AND s.sku=l.sku WHERE l.provider_id=:p AND l.state!='inactive' ORDER BY l.id FOR UPDATE OF l",
                p=provider,
            )
            for link in links:
                enqueue(
                    conn,
                    dict(link, run_id=run_id),
                    0 if link["cut_requested"] else link["source_quantity"],
                )
            checkpoint("enqueued_in_transaction")
            execute(
                conn,
                "UPDATE comparison_events SET processed_at=now() WHERE provider_id=:p AND processed_at IS NULL",
                p=provider,
            )
        checkpoint("comparison_committed")
    return True
