"""Estado interno y consultas compartidas por API, muestreador y tablero.

Las consultas son de sólo lectura. Únicamente sample() persiste una muestra por minuto.
"""

import json
from datetime import UTC, datetime, timedelta

from ivostock.db import execute, ownership, rows
from ivostock.health import WORKERS, worker_components
from ivostock.probes import http_components
from ivostock.services import monitor, runs_summary

RETENTION = timedelta(days=7)
COMPONENTS = ("api", "simulator", "provider", *WORKERS)


def minute(at):
    return at.astimezone(UTC).replace(second=0, microsecond=0)


def window(start=None, end=None):
    end = end or minute(datetime.now(UTC))
    start = start or end - timedelta(hours=24)
    if any(at.tzinfo is None or at.second or at.microsecond for at in (start, end)):
        raise ValueError("El período requiere fechas con zona horaria y minutos completos")
    if not timedelta(0) < end - start <= RETENTION:
        raise ValueError("El período debe ser positivo y no superar siete días")
    if end > minute(datetime.now(UTC)):
        raise ValueError("El período no puede incluir minutos futuros o incompletos")
    return start, end


def publications(conn, start, end):
    # El denominador son revisiones publicables, nunca intentos HTTP. Cada tienda aparece
    # incluso sin muestras. Los pendientes y duraciones desconocidas se informan aparte.
    return [
        dict(r)
        for r in rows(
            conn,
            """
        WITH measured AS (
            SELECT *,extract(epoch FROM effect_at-origin_at)::float8 AS seconds
            FROM publication_measurements
            WHERE COALESCE(origin_at,recorded_at)>=:start
              AND COALESCE(origin_at,recorded_at)<:end
        )
        SELECT s.id AS store_id,
            count(m.link_id) AS revisions,
            count(m.link_id) FILTER (WHERE m.superseded_at IS NOT NULL) AS superseded,
            count(m.link_id) FILTER (WHERE m.superseded_at IS NULL
                AND m.confirmed_at IS NULL) AS pending,
            count(m.link_id) FILTER (WHERE m.superseded_at IS NULL
                AND m.confirmed_at IS NOT NULL
                AND (m.seconds IS NULL OR m.seconds<0)) AS unknown_duration,
            count(m.link_id) FILTER (WHERE m.superseded_at IS NULL
                AND m.seconds>=0) AS samples,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY m.seconds)
                FILTER (WHERE m.superseded_at IS NULL AND m.seconds>=0) AS p95_seconds,
            percentile_cont(0.99) WITHIN GROUP (ORDER BY m.seconds)
                FILTER (WHERE m.superseded_at IS NULL AND m.seconds>=0) AS p99_seconds,
            max(extract(epoch FROM clock_timestamp()-m.origin_at)::float8)
                FILTER (WHERE m.superseded_at IS NULL
                    AND m.confirmed_at IS NULL) AS oldest_pending_seconds
        FROM stores s LEFT JOIN measured m ON m.store_id=s.id
        GROUP BY s.id ORDER BY s.id
    """,
            start=start,
            end=end,
        )
    ]


def sample(engine, check_http=http_components):
    """Un único escritor; una caída deja un minuto faltante, nunca un éxito inventado."""
    with ownership(engine, "metrics:sampler") as conn:
        if conn is None:
            return False
        at = datetime.now(UTC)
        bucket = minute(at)
        with conn.begin():
            if rows(conn, "SELECT 1 FROM metric_samples WHERE minute=:m", m=bucket):
                return False
        components = check_http()
        operations = monitor(engine)
        ingestion = runs_summary(engine)
        with conn.begin():
            components.update(worker_components(conn))
            payload = {
                "at": at,
                "components": components,
                "operations": operations,
                "ingestion": ingestion,
                "publication": publications(conn, at - timedelta(hours=24), at),
            }
            execute(
                conn,
                "INSERT INTO metric_samples(minute,payload) VALUES (:m,CAST(:p AS jsonb)) "
                "ON CONFLICT DO NOTHING",
                m=bucket,
                p=json.dumps(payload, default=str),
            )
            execute(conn, "DELETE FROM metric_samples WHERE minute<:cut", cut=bucket - RETENTION)
            execute(
                conn,
                "DELETE FROM publication_measurements "
                "WHERE COALESCE(confirmed_at,superseded_at)<:cut",
                cut=at - RETENTION,
            )
    return True


def current(engine):
    with engine.begin() as conn:
        found = rows(
            conn,
            "SELECT minute,payload,extract(epoch FROM clock_timestamp()-minute) "
            "AS age_seconds FROM metric_samples ORDER BY minute DESC LIMIT 1",
        )
        workers = worker_components(conn)
    if not found:
        return {"minute": None, "age_seconds": None, "state": None, "workers": workers}
    last = found[0]
    return {
        "minute": last["minute"],
        "age_seconds": float(last["age_seconds"]),
        "state": last["payload"],
        "workers": workers,
    }


def history(engine, start=None, end=None):
    start, end = window(start, end)
    with engine.begin() as conn:
        found = rows(
            conn,
            "SELECT minute,payload FROM metric_samples "
            "WHERE minute>=:a AND minute<:b ORDER BY minute",
            a=start,
            b=end,
        )
    return {"start": start, "end": end, "samples": [dict(r) for r in found]}


def summary(engine, start=None, end=None):
    start, end = window(start, end)
    expected = int((end - start).total_seconds() / 60)
    with engine.begin() as conn:
        measured = rows(
            conn,
            "SELECT payload->'components' AS components FROM metric_samples "
            "WHERE minute>=:a AND minute<:b ORDER BY minute",
            a=start,
            b=end,
        )
        publication = publications(conn, start, end)
    successes = dict.fromkeys((*COMPONENTS, "engine"), 0)
    for sample_row in measured:
        components = sample_row["components"]
        for name in COMPONENTS:
            successes[name] += components.get(name, {}).get("available") is True
        successes["engine"] += all(components.get(w, {}).get("available") is True for w in WORKERS)
    return {
        "start": start,
        "end": end,
        "expected_samples": expected,
        "recorded_samples": len(measured),
        "missing_samples": expected - len(measured),
        "availability": {
            name: {"successful_samples": count, "availability_percent": 100 * count / expected}
            for name, count in successes.items()
        },
        "publication": publication,
    }
