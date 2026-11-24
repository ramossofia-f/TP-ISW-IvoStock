"""El monitoreo técnico reutiliza el reporte y las sondas reales de ML del PR #18."""

import json

import httpx
import pytest

from ivostock import metrics, services
from ivostock.db import execute
from ivostock.health import WORKERS, worker_components
from ivostock.ml import training
from ivostock.ml.repository import report
from ivostock.probes import probe
from ivostock.worker import heartbeat
from tests.ml.test_lifecycle import ml_server as ml_server

pytestmark = pytest.mark.integration


def ml_checks(server):
    return dict(
        probe(name, server.url + path)
        for name, path in (
            ("ml", "/health/live"),
            ("ml_ready", "/health"),
        )
    )


def test_cold_model_is_distinct_from_live_service_and_available_engine(engine, ml_server):
    for name in (*WORKERS, "ml-train"):
        heartbeat(engine, name)
    assert metrics.sample(engine, lambda: ml_checks(ml_server))
    current = metrics.current(engine)
    assert current["state"]["components"]["ml"]["available"]
    assert not current["state"]["components"]["ml_ready"]["available"]
    assert all(current["workers"][name]["available"] for name in (*WORKERS, "ml-train"))
    assert current["state"]["ml"]["configured"]
    assert current["state"]["ml"]["active_model"] is None
    assert current["state"]["ml"]["learning"]["accepted_observations"] == 0
    assert report(engine)["learning"]["accepted_observations"] == 0


def test_ready_model_report_is_persisted_only_in_technical_monitoring(
    engine, ml_server, feed_server, api
):
    provider = services.add_provider(engine, "Proveedor ML", feed_server["url"])["id"]
    for _ in range(10):
        assert services.ingest(engine, provider)["status"] == "accepted"
        assert training.train_once(engine)
    heartbeat(engine, "ml-train")
    expected = report(engine)
    assert metrics.sample(engine, lambda: ml_checks(ml_server))
    state = api.get("/metrics/current").json()["state"]
    assert state["components"]["ml_ready"]["available"]
    assert state["ml"]["active_model"]["version"] == expected["active_model"]["version"]
    assert state["ml"]["active_model"]["min_runs"] == 10
    assert state["ml"]["active_model"]["counts"][str(provider)] == 10
    assert state["ml"]["learning"]["pending"] == 0
    assert report(engine)["learning"]["accepted_observations"] == 10
    # Los recorridos de negocio siguen filtrando la instrumentación técnica.
    runs = api.get("/runs").json()
    assert '"ml"' not in json.dumps(runs)
    assert expected["active_model"]["version"] not in json.dumps(runs)


def test_training_health_uses_its_own_thirty_second_heartbeat(engine, ml_server):
    for name in (*WORKERS, "ml-train"):
        heartbeat(engine, name)
    with engine.begin() as conn:
        execute(
            conn,
            "UPDATE worker_heartbeats SET at=clock_timestamp()-interval '31 seconds' "
            "WHERE name='ml-train'",
        )
        workers = worker_components(conn)
    assert all(workers[name]["available"] for name in WORKERS)
    assert not workers["ml-train"]["available"]
    assert httpx.get(ml_server.url + "/health/training").status_code == 503
    assert httpx.get(ml_server.url + "/health/live").status_code == 200
