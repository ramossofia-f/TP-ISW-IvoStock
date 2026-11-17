import sys

from ivostock.db import database, rows


def main():
    seconds = 30 if sys.argv[1] == "ml-train" else 660
    with database().begin() as conn:
        found = rows(
            conn,
            "SELECT 1 FROM worker_heartbeats WHERE name=:n "
            "AND at>now()-:seconds*interval '1 second'",
            n=sys.argv[1],
            seconds=seconds,
        )
    raise SystemExit(0 if found else 1)


if __name__ == "__main__":
    main()
