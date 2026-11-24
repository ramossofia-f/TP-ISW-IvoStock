import sys

from ivostock.db import database, rows

WORKERS = ("ingest", "compare", "publish", "catalog")
HEARTBEAT_SECONDS = 660
WORKER_LIMITS = dict.fromkeys(WORKERS, HEARTBEAT_SECONDS) | {"ml-train": 30}


def worker_components(conn):
    found = {
        r["name"]: r
        for r in rows(
            conn,
            "SELECT name,at,extract(epoch FROM clock_timestamp()-at) AS age_seconds "
            "FROM worker_heartbeats",
        )
    }
    return {
        name: {
            "available": name in found and float(found[name]["age_seconds"]) < limit,
            "last_seen_at": found[name]["at"] if name in found else None,
            "age_seconds": float(found[name]["age_seconds"]) if name in found else None,
        }
        for name, limit in WORKER_LIMITS.items()
    }


def main():
    with database().begin() as conn:
        available = worker_components(conn).get(sys.argv[1], {}).get("available", False)
    raise SystemExit(0 if available else 1)


if __name__ == "__main__":
    main()
