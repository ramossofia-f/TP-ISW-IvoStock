"""Entrenamiento reproducible con aceptados; sklearn sólo se importa en este trabajador."""

import json
import logging
import os
from collections import Counter

from ivostock.db import execute, ownership, rows
from ivostock.failpoints import checkpoint
from ivostock.ml.config import TrainingConfig
from ivostock.ml.normalidad import (
    FEATURES,
    SCHEMA,
    NormalityModel,
    digest,
    numeric,
    timestamp,
    window,
)

log = logging.getLogger("ivostock.ml.training")


def fit(observations, config):
    import numpy as np
    import sklearn
    from sklearn.svm import OneClassSVM

    selected = window(observations, config)
    if not selected:
        raise ValueError("No hay observaciones sanas para entrenar")
    reference = max(timestamp(o["accepted_at"]) for o in selected)
    # El tiempo es el de aceptación, no el del reintento: la reproducción no depende del reloj.
    ages = np.array([(reference - timestamp(o["accepted_at"])).total_seconds() for o in selected])
    weights = np.exp2(np.maximum(-ages / (config.half_life_days * 86400), -1000))
    weights *= len(weights) / weights.sum()
    providers = sorted({o["provider_id"] for o in selected})
    raw = np.array([numeric(o["features"]) for o in selected], dtype=float)
    means = np.average(raw, axis=0, weights=weights)
    # La varianza centrada evita cancelación y raíces negativas en columnas constantes.
    scales = np.sqrt(np.average((raw - means) ** 2, axis=0, weights=weights))
    scales = np.where(scales > 1e-12, scales, 1.0)
    one_hot = np.array([[float(o["provider_id"] == p) for p in providers] for o in selected])
    x = np.column_stack(((raw - means) / scales, one_hot))
    model = OneClassSVM(nu=config.nu, gamma="scale", kernel="rbf").fit(x, sample_weight=weights)
    if model.fit_status_ != 0:
        raise ValueError("El entrenamiento ML no convergió")
    dataset = [
        {**o, "accepted_at": timestamp(o["accepted_at"]).isoformat()}
        for o in selected
    ]
    payload = {
        "schema": SCHEMA, "features": list(FEATURES), "config": config.to_dict(),
        "providers": providers, "counts": dict(Counter(str(o["provider_id"]) for o in selected)),
        "means": means.tolist(), "scales": scales.tolist(),
        "support_vectors": model.support_vectors_.tolist(),
        "dual_coef": model.dual_coef_[0].tolist(), "intercept": float(model.intercept_[0]),
        "gamma": float(model._gamma), "reference_at": reference.isoformat(),
        "run_ids": [o["run_id"] for o in selected], "dataset_hash": digest(dataset),
        "libraries": {"sklearn": sklearn.__version__, "numpy": np.__version__},
    }
    payload["version"] = digest(payload)
    exported = NormalityModel(payload)
    if not np.allclose(
        [exported.score(o["provider_id"], o["features"]) for o in selected],
        model.decision_function(x), rtol=1e-9, atol=1e-9,
    ):
        raise ValueError("La exportación ML no coincide con sklearn")
    return payload


def train_once(engine):
    """Publicar modelo y confirmar una observación juntos; el lock se libera al morir el proceso."""
    with ownership(engine, "ml:training") as conn:
        if conn is None:
            return False
        with conn.begin():
            pending = rows(
                conn,
                "SELECT run_id FROM ml_observations WHERE trained_version IS NULL "
                "ORDER BY accepted_at,run_id LIMIT 1",
            )
            if not pending:
                return False
            run_id = pending[0]["run_id"]
            if not rows(conn, "SELECT 1 FROM ml_observations WHERE run_id=:r "
                        "AND retry_at<=clock_timestamp()", r=run_id):
                return False
        checkpoint("ml_training_claimed")
        try:
            config = TrainingConfig.from_env()
            with conn.begin():
                observations = [dict(r) for r in rows(
                    conn,
                    "SELECT run_id,provider_id,accepted_at,features FROM ("
                    " SELECT *,row_number() OVER(PARTITION BY provider_id "
                    " ORDER BY accepted_at DESC,run_id DESC) AS position FROM ml_observations"
                    " WHERE trained_version IS NOT NULL OR run_id=:r) candidates"
                    " WHERE position<=:n ORDER BY accepted_at,run_id",
                    r=run_id, n=config.history_per_provider,
                )]
            payload = fit(observations, config)
            checkpoint("ml_model_fitted")
            with conn.begin():
                execute(conn, "INSERT INTO ml_models(version,payload) VALUES (:v,CAST(:p AS jsonb))",
                        v=payload["version"], p=json.dumps(payload, allow_nan=False))
                execute(conn, "UPDATE ml_state SET active_version=:v WHERE id=1",
                        v=payload["version"])
                execute(conn, "UPDATE ml_observations SET trained_version=:v,trained_at=now(),"
                        "last_error=NULL WHERE run_id=:r", v=payload["version"], r=run_id)
                checkpoint("ml_publishing_in_transaction")
        except Exception as exc:
            try:
                retry = max(1, int(os.getenv("ML_RETRY_SECONDS", "30")))
            except ValueError:
                retry = 30
            with conn.begin():
                execute(conn, "UPDATE ml_observations SET attempts=attempts+1,last_error=:e,"
                        "retry_at=clock_timestamp()+:seconds*interval '1 second' WHERE run_id=:r",
                        e=type(exc).__name__, seconds=retry, r=run_id)
            log.error("Reentrenamiento pendiente", extra={"component": "ml-train", "run": run_id,
                                                         "error": type(exc).__name__})
            return False
        checkpoint("ml_model_published")
        log.info("Modelo global actualizado", extra={"component": "ml-train", "run": run_id,
                                                   "model_version": payload["version"]})
        return True


def reproduce(engine, version):
    with engine.begin() as conn:
        found = rows(conn, "SELECT payload FROM ml_models WHERE version=:v", v=version)
        if not found:
            raise ValueError("Versión ML inexistente")
        payload = found[0]["payload"]
        observations = [dict(r) for r in rows(
            conn, "SELECT run_id,provider_id,accepted_at,features FROM ml_observations "
            "WHERE run_id=ANY(:ids)", ids=payload["run_ids"],
        )]
    rebuilt = fit(observations, TrainingConfig(**payload["config"]))
    if rebuilt["version"] != version:
        raise ValueError("La reproducción difiere; comprobar datos y versiones de bibliotecas")
    return rebuilt
