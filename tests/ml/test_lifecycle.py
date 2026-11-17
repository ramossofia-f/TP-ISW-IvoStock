"""Circuito final por HTTP/TCP, PostgreSQL y S3 reales, siempre sobre ivostock_test."""

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest
from sqlalchemy.exc import DBAPIError

from ivostock import cli, services
from ivostock.db import execute, rows
from ivostock.ml import training
from ivostock.ml.repository import active_model, observe, report
from tests.helpers import admin, drain, import_catalogs, seed

pytestmark = pytest.mark.integration


def scalar(engine, sql, **params):
    with engine.begin() as conn:
        return rows(conn, sql, **params)[0]


class MLServer:
    def __init__(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.process = None

    def start(self):
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ivostock.ml.api:app", "--host", "127.0.0.1",
             "--port", str(self.port), "--log-level", "error"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            assert self.process.poll() is None, "El servicio ML no pudo iniciar"
            try:
                if httpx.get(self.url + "/health/live", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        raise AssertionError("El servicio ML no inició en quince segundos")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)


@pytest.fixture
def ml_server(engine, monkeypatch):
    server = MLServer()
    monkeypatch.setenv("ML_TOKEN", "isolated-ml-token")
    monkeypatch.setenv("ML_URL", server.url)
    monkeypatch.setenv("ML_MIN_RUNS", "10")
    server.start()
    try:
        yield server
    finally:
        server.stop()


def world(engine, feed_server):
    seed("T1", 3)
    services.add_store(engine, "T1")
    import_catalogs(engine)
    provider = services.add_provider(engine, "P", feed_server["url"])["id"]
    services.approve(engine, provider, "T1", count=3)
    return provider


def warm(engine, feed_server, provider):
    for n in range(10):
        feed_server["write"]({**feed_server["stock"], "A000": 10 + n})
        run = services.ingest(engine, provider)
        assert run["status"] == "accepted"
        assert training.train_once(engine)
        services.compare_once(engine)
        drain(engine)
    assert active_model(engine).ready(provider)


def test_accepted_run_propagates_before_asynchronous_training(engine, feed_server, ml_server):
    provider = world(engine, feed_server)
    warm(engine, feed_server, provider)
    version = active_model(engine).version
    feed_server["write"]({**feed_server["stock"], "A000": 25})
    run = services.ingest(engine, provider)
    decision = scalar(engine, "SELECT metrics->'ml' AS ml FROM runs WHERE id=:r", r=run["id"])["ml"]
    assert run["status"] == "accepted" and decision["source"] == "ml"
    assert decision["version"] == version == active_model(engine).version
    assert report(engine)["learning"]["pending"] == 1
    services.compare_once(engine)
    drain(engine)
    assert admin("/admin/stores/T1")[0]["available_quantity"] == 25
    assert training.train_once(engine) and active_model(engine).version != version
    assert not training.train_once(engine) and report(engine)["learning"]["pending"] == 0


def test_anomaly_has_no_event_no_learning_and_no_public_ml_metrics(
    engine, api, feed_server, ml_server,
):
    provider = world(engine, feed_server)
    warm(engine, feed_server, provider)
    previous = report(engine)["learning"]["accepted_observations"]
    events = scalar(engine, "SELECT count(*) AS n FROM comparison_events")["n"]
    # Volumen imposible respecto de la referencia; D=Z=p=0: las reglas lo aceptarían.
    expanded = {**feed_server["stock"], **{f"NEW{n}": 10 for n in range(500)}, "A000": 999}
    feed_server["write"](expanded)
    run = services.ingest(engine, provider)
    assert run["status"] == "quarantined"
    assert report(engine)["learning"]["accepted_observations"] == previous
    assert scalar(engine, "SELECT count(*) AS n FROM comparison_events")["n"] == events
    assert scalar(engine, "SELECT count(*) AS n FROM stock")["n"] == 50
    assert services.status(engine, "tasks") == []
    assert admin("/admin/stores/T1")[0]["available_quantity"] == 19
    assert api.get("/providers").json()[0]["quarantine_run_id"] == run["id"]
    public = api.get("/runs").json()["items"][0]
    assert public["status"] == "quarantined" and public["metrics"]["p"] == 0
    assert not ({"ml", "score", "version", "model_version"} & public["metrics"].keys())
    feed_server["write"]({**feed_server["stock"], "A000": 20})
    assert services.ingest(engine, provider)["status"] == "accepted"
    assert api.get("/providers").json()[0]["quarantine_run_id"] is None


def test_outage_keeps_learning_and_recovery_processes_it_once(engine, feed_server, ml_server):
    provider = world(engine, feed_server)
    warm(engine, feed_server, provider)
    old_version = active_model(engine).version
    ml_server.stop()
    for quantity in (20, 21, 22):
        feed_server["write"]({**feed_server["stock"], "A000": quantity})
        run = services.ingest(engine, provider)
        assert run["status"] == "accepted"
        decision = scalar(engine, "SELECT metrics->'ml' AS ml FROM runs WHERE id=:r", r=run["id"])["ml"]
        assert decision["source"] == "rules" and decision["fallback_reason"] == "unavailable"
        services.compare_once(engine)
        drain(engine)
    assert report(engine)["learning"]["pending"] == 3
    assert active_model(engine).version == old_version
    assert admin("/admin/stores/T1")[0]["available_quantity"] == 22
    # El respaldo tampoco aprende de una cuarentena.
    feed_server["write"]({})
    assert services.ingest(engine, provider)["status"] == "quarantined"
    assert report(engine)["learning"]["pending"] == 3
    ml_server.start()
    assert sum(training.train_once(engine) for _ in range(4)) == 3
    assert report(engine)["learning"]["pending"] == 0
    assert report(engine)["learning"]["accepted_observations"] == 13


def test_new_provider_uses_rules_until_its_tenth_observation_is_trained(
    engine, feed_server, ml_server,
):
    provider = world(engine, feed_server)
    warm(engine, feed_server, provider)
    provider2 = services.add_provider(engine, "P2", feed_server["url"])["id"]
    for n in range(10):
        run = services.ingest(engine, provider2)
        decision = scalar(engine, "SELECT metrics->'ml' AS ml FROM runs WHERE id=:r", r=run["id"])["ml"]
        assert decision["fallback_reason"] == "insufficient_history"
        assert training.train_once(engine)
        assert active_model(engine).ready(provider2) is (n == 9)
    run = services.ingest(engine, provider2)
    assert scalar(engine, "SELECT metrics->'ml'->>'source' AS source FROM runs WHERE id=:r",
                  r=run["id"])["source"] == "ml"


def test_live_readiness_and_trainer_probes_are_separate(engine, feed_server, ml_server):
    assert httpx.get(ml_server.url + "/health/live").status_code == 200
    assert httpx.get(ml_server.url + "/health").status_code == 503
    assert httpx.get(ml_server.url + "/health/training").status_code == 503
    provider = world(engine, feed_server)
    warm(engine, feed_server, provider)
    assert httpx.get(ml_server.url + "/health").json() == {"status": "ok"}
    from ivostock.worker import heartbeat
    heartbeat(engine, "ml-train")
    assert httpx.get(ml_server.url + "/health/training").json() == {"status": "ok"}


def test_failure_preserves_active_version_and_retries_later(engine, feed_server, monkeypatch):
    provider = services.add_provider(engine, "P", feed_server["url"])["id"]
    services.ingest(engine, provider)
    assert training.train_once(engine)
    old_version = active_model(engine).version
    run = services.ingest(engine, provider)
    with monkeypatch.context() as patch:
        def fail(*args):
            raise RuntimeError("private-url-and-token")
        patch.setattr(training, "fit", fail)
        assert not training.train_once(engine)
    result = report(engine)
    assert result["active_model"]["version"] == old_version
    assert result["training_failures"][0]["last_error"] == "RuntimeError"
    assert result["learning"]["pending"] == 1 and not training.train_once(engine)
    with engine.begin() as conn:
        execute(conn, "UPDATE ml_observations SET retry_at=now() WHERE run_id=:r", r=run["id"])
    assert training.train_once(engine) and active_model(engine).version != old_version


def test_observation_identity_and_immutable_models_and_reproduction(
    engine, feed_server, tmp_path,
):
    provider = services.add_provider(engine, "P", feed_server["url"])["id"]
    run = services.ingest(engine, provider)
    metrics = scalar(engine, "SELECT metrics FROM runs WHERE id=:r", r=run["id"])["metrics"]
    with engine.begin() as conn:
        observe(conn, run["id"], provider, metrics)
    assert report(engine)["learning"]["accepted_observations"] == 1
    assert training.train_once(engine)
    version = active_model(engine).version
    with pytest.raises(DBAPIError), engine.begin() as conn:
        execute(conn, "UPDATE ml_models SET payload='{}'")
    output = tmp_path / "reproduced.json"
    result = cli.run(cli.parser().parse_args(["ml-reproduce", version, "--output", str(output)]))
    assert result["activated"] is False and output.exists()
    assert active_model(engine).version == version and not training.train_once(engine)


def test_invalid_contract_never_trains_and_disable_clears_notice(engine, api, feed_server):
    provider = services.add_provider(engine, "P", feed_server["url"])["id"]
    services.ingest(engine, provider)
    feed_server["path"].write_bytes(b"wrong-header\nA;1\n")
    assert services.ingest(engine, provider)["status"] == "failed"
    assert report(engine)["learning"]["accepted_observations"] == 1
    feed_server["write"]({})
    quarantined = services.ingest(engine, provider)
    assert api.get("/providers").json()[0]["quarantine_run_id"] == quarantined["id"]
    services.cut(engine, provider)
    assert api.get("/providers").json()[0]["quarantine_run_id"] is None


def crash_at(tmp_path, point, argv):
    marker = tmp_path / point
    env = {**os.environ, "IVO_FAILPOINT": point, "IVO_FAILPOINT_MARKER": str(marker)}
    process = subprocess.Popen([sys.executable, *argv], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            assert process.poll() is None, f"El proceso terminó antes de {point}"
            time.sleep(0.02)
        assert marker.exists(), point
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


@pytest.mark.parametrize("point", [
    "ml_training_claimed", "ml_model_fitted", "ml_publishing_in_transaction", "ml_model_published",
])
def test_abrupt_training_crash_keeps_one_publication(engine, feed_server, tmp_path, point):
    provider = services.add_provider(engine, "P", feed_server["url"])["id"]
    services.ingest(engine, provider)
    crash_at(tmp_path, point, ["-m", "ivostock.worker", "ml-train", "--once"])
    training.train_once(engine)
    assert report(engine)["learning"]["pending"] == 0
    assert scalar(engine, "SELECT count(*) AS n FROM ml_models")["n"] == 1
    assert active_model(engine).payload["run_ids"] == [1]
    assert not training.train_once(engine)


def test_acceptance_and_learning_outbox_rollback_together(engine, feed_server, tmp_path):
    provider = services.add_provider(engine, "P", feed_server["url"])["id"]
    crash_at(tmp_path, "ml_observation_in_transaction",
             ["-m", "ivostock.cli", "ingest", str(provider)])
    assert report(engine)["learning"]["accepted_observations"] == 0
    assert scalar(engine, "SELECT count(*) AS n FROM comparison_events")["n"] == 0
    assert scalar(engine, "SELECT count(*) AS n FROM stock")["n"] == 0
    assert services.ingest(engine, provider)["status"] == "accepted"
    assert report(engine)["learning"]["accepted_observations"] == 1
