import argparse
import json
import sys
import time

from ivostock.db import database, execute, rows
from ivostock.logs import configurar
from ivostock.publisher import publish_once
from ivostock.services import compare_once, import_page, ingest


def heartbeat(engine, name):
    with engine.begin() as conn:
        execute(
            conn,
            "INSERT INTO worker_heartbeats(name) VALUES (:n) ON CONFLICT(name) DO UPDATE SET at=now()",
            n=name,
        )


def tick(engine, kind):
    heartbeat(engine, kind)
    if kind == "compare":
        return compare_once(engine)
    if kind == "publish":
        return publish_once(engine)
    if kind == "catalog":
        return import_page(engine)
    with engine.begin() as conn:
        due = rows(
            conn,
            "SELECT id FROM providers WHERE active AND (next_run_at<=now() OR EXISTS (SELECT 1 FROM runs WHERE provider_id=providers.id AND status='running')) ORDER BY next_run_at",
        )
    any_due_completed = False
    for provider in due:
        result = ingest(engine, provider["id"], scheduled=True)
        any_due_completed |= result["status"] not in ("busy", "not_due")
        print(json.dumps({"component": kind, "provider": provider["id"], **result}), flush=True)
        heartbeat(engine, kind)
    return any_due_completed


def main():
    configurar(sys.stdout)
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["ingest", "compare", "publish", "catalog"])
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    engine = database()
    while True:
        try:
            worked = tick(engine, args.kind)
        except Exception as exc:
            print(json.dumps({"component": args.kind, "error": type(exc).__name__}), flush=True)
            if args.once:
                raise SystemExit(1) from None
            time.sleep(2)
            continue
        if args.once:
            break
        if not worked:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
