"""Lecturas y outbox de aprendizaje; sin importar sklearn en ingesta/API."""

import json

from ivostock.db import execute, rows
from ivostock.ml.normalidad import NormalityModel, features


def observe(conn, run_id, provider, metrics):
    execute(
        conn,
        "INSERT INTO ml_observations(run_id,provider_id,features) "
        "SELECT id,provider_id,CAST(:f AS jsonb) FROM runs "
        "WHERE id=:r AND provider_id=:p AND status='accepted' ON CONFLICT(run_id) DO NOTHING",
        r=run_id, p=provider, f=json.dumps(features(metrics), allow_nan=False),
    )


def active_model(engine):
    with engine.begin() as conn:
        found = rows(conn, "SELECT payload FROM ml_models m JOIN ml_state s "
                     "ON m.version=s.active_version WHERE s.id=1")
    return NormalityModel(found[0]["payload"]) if found else None


def report(engine):
    with engine.begin() as conn:
        model = rows(conn, "SELECT m.version,m.created_at,m.payload->'counts' AS counts,"
                     "m.payload->'config'->'min_runs' AS min_runs "
                     "FROM ml_models m JOIN ml_state s ON m.version=s.active_version WHERE s.id=1")
        learning = dict(rows(conn, "SELECT count(*) AS accepted_observations,"
                             "count(*) FILTER(WHERE trained_version IS NULL) AS pending,"
                             "min(accepted_at) FILTER(WHERE trained_version IS NULL) AS oldest_pending,"
                             "max(trained_at) AS last_training FROM ml_observations")[0])
        decisions = [dict(r) for r in rows(
            conn, "SELECT metrics->'ml'->>'source' AS source,"
            "metrics->'ml'->>'fallback_reason' AS fallback_reason,status,count(*) AS count "
            "FROM runs WHERE metrics ? 'ml' GROUP BY 1,2,3 ORDER BY 1,2,3",
        )]
        scores = dict(rows(conn, "SELECT count(*) AS count,min(score) AS min,max(score) AS max,"
                           "percentile_cont(0.5) WITHIN GROUP(ORDER BY score) AS median,"
                           "percentile_cont(0.95) WITHIN GROUP(ORDER BY score) AS p95 FROM ("
                           "SELECT (metrics->'ml'->>'score')::double precision AS score FROM runs "
                           "WHERE metrics->'ml'->>'source'='ml' ORDER BY id DESC LIMIT 1000) recent")[0])
        failures = [dict(r) for r in rows(
            conn, "SELECT run_id,attempts,last_error,retry_at FROM ml_observations "
            "WHERE last_error IS NOT NULL ORDER BY accepted_at LIMIT 20",
        )]
    return {"active_model": dict(model[0]) if model else None, "learning": learning,
            "decisions": decisions, "recent_scores": scores, "training_failures": failures}
