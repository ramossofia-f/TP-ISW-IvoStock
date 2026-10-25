"""Ventana móvil compartida y durable; un permiso se consume antes del envío."""

from ivostock.db import execute, rows


def reserve(engine, store_id, simulator=False):
    table = "sim_calls" if simulator else "market_calls"
    with engine.begin() as conn:
        execute(
            conn,
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            key=f"{table}:{store_id}",
        )
        execute(
            conn,
            f"DELETE FROM {table} WHERE store_id=:s AND at <= clock_timestamp()-interval '60 seconds'",
            s=store_id,
        )
        result = rows(
            conn,
            f"SELECT count(*) AS n, EXTRACT(EPOCH FROM min(at)+interval '60 seconds'-clock_timestamp()) AS wait FROM {table} WHERE store_id=:s",
            s=store_id,
        )[0]
        if result["n"] >= 60:
            return max(0.05, float(result["wait"]))
        execute(conn, f"INSERT INTO {table}(store_id) VALUES (:s)", s=store_id)
    return 0.0
