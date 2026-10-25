import sys

from ivostock.db import database, rows


def main():
    with database().begin() as conn:
        found = rows(
            conn,
            "SELECT 1 FROM worker_heartbeats WHERE name=:n AND at>now()-interval '11 minutes'",
            n=sys.argv[1],
        )
    raise SystemExit(0 if found else 1)


if __name__ == "__main__":
    main()
