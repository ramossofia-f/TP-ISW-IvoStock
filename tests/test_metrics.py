"""Métricas durables, percentiles de efecto externo y separación de disponibilidad."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from ivostock import metrics, services
from ivostock.config import Settings
from ivostock.db import execute, rows
from ivostock.health import WORKERS
from ivostock.publisher import publish_once
from tests.helpers import admin, drain
from tests.test_pipeline import setup_world


def period():
    end = metrics.minute(datetime.now(UTC))
    return end - timedelta(minutes=3), end


@pytest.mark.parametrize(
    "start,end",
    [
        (datetime(2026, 1, 1), datetime(2026, 1, 2)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 9, tzinfo=UTC)),
        (datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_invalid_windows_are_rejected(start, end):
    with pytest.raises(ValueError):
        metrics.window(start, end)


def test_metrics_health_and_authentication_do_not_depend_on_the_main_api():
    from ivostock.metrics_service import app

    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    for path in ("/metrics/current", "/metrics/history", "/metrics/summary", "/openapi.json", "/auth/me"):
        assert client.get(path).status_code == 401
    assert client.get("/docs").status_code == 404
    response = client.post("/auth/login", json={"username": "x" * 65, "password": "private"})
    assert response.status_code == 404
    assert "private" not in response.text and '"input"' not in response.text
    assert client.post("/auth/logout").status_code == 404


@pytest.mark.integration
def test_minute_sampling_is_unique_and_read_endpoints_do_not_write(engine):
    def good():
        return {name: {"available": True} for name in ("api", "simulator", "provider")}

    assert metrics.sample(engine, good)
    assert not metrics.sample(engine, lambda: pytest.fail("El minuto ya fue registrado"))
    for _ in range(2):
        current = metrics.current(engine)
        assert current["state"]["operations"]["links"]["pending"] == 0
        assert not current["workers"]["publish"]["available"]
        metrics.history(engine)
        metrics.summary(engine)
    with engine.begin() as conn:
        assert rows(conn, "SELECT count(*) AS n FROM metric_samples")[0]["n"] == 1


@pytest.mark.integration
def test_availability_has_a_fixed_denominator_and_keeps_api_and_engine_separate(engine):
    start, end = period()
    workers = {name: {"available": True} for name in WORKERS}
    with engine.begin() as conn:
        for offset, api in ((0, True), (1, False)):
            execute(
                conn,
                "INSERT INTO metric_samples(minute,payload) VALUES (:m,CAST(:p AS jsonb))",
                m=start + timedelta(minutes=offset),
                p=json.dumps({"components": {**workers, "api": {"available": api}}}),
            )
    summary = metrics.summary(engine, start, end)
    assert summary["expected_samples"] == 3
    assert summary["missing_samples"] == 1
    assert summary["availability"]["api"]["availability_percent"] == pytest.approx(100 / 3)
    assert summary["availability"]["engine"]["availability_percent"] == pytest.approx(200 / 3)
    assert summary["availability"]["ml_ready"]["availability_percent"] == 0


@pytest.mark.integration
def test_retention_removes_only_samples_older_than_seven_days(engine):
    now = metrics.minute(datetime.now(UTC))
    with engine.begin() as conn:
        for at in (now - timedelta(days=7, minutes=1), now - timedelta(days=6)):
            execute(conn, "INSERT INTO metric_samples VALUES (:at,'{}')", at=at)
    metrics.sample(engine, lambda: {})
    with engine.begin() as conn:
        remaining = rows(conn, "SELECT minute FROM metric_samples ORDER BY minute")
    assert len(remaining) == 2 and remaining[0]["minute"] == now - timedelta(days=6)


@pytest.mark.integration
def test_percentiles_are_per_store_from_origin_to_external_effect(engine, feed_server):
    provider = setup_world(engine, feed_server)
    admin(
        "/admin/seed",
        {
            "store": "T2",
            "items": [
                {"id": "I0", "sku": "A000", "available_quantity": 0},
            ],
        },
    )
    services.add_store(engine, "T2")
    services.approve(engine, provider, "T2")
    services.compare_once(engine)
    with engine.begin() as conn:
        execute(
            conn,
            "UPDATE publication_measurements SET origin_at=clock_timestamp()-"
            "CASE WHEN store_id='T1' THEN interval '45 minutes' ELSE interval '10 minutes' END",
        )
    drain(engine)
    with engine.begin() as conn:
        stores = metrics.publications(
            conn, datetime.now(UTC) - timedelta(days=1), datetime.now(UTC)
        )
    assert [s["store_id"] for s in stores] == ["T1", "T2"]
    assert [s["samples"] for s in stores] == [1, 1]
    assert stores[0]["p95_seconds"] == pytest.approx(2700, abs=10)
    assert stores[1]["p99_seconds"] == pytest.approx(600, abs=10)
    assert all(s["pending"] == 0 for s in stores)


@pytest.mark.integration
def test_lost_ack_reuses_the_first_external_effect_without_duplicating_samples(engine, feed_server):
    setup_world(engine, feed_server)
    cfg = Settings.from_env()
    task = services.status(engine, "tasks")[0]
    # Primer efecto remoto cuyo acuse no procesa el publicador local (pérdida simulada).
    response = httpx.put(
        cfg.simulator_url + "/stores/T1/items/I0/stock",
        headers={
            "Authorization": "Bearer " + cfg.simulator_token,
            "X-Ivo-Work": f"{task['link_id']}:{task['revision']}",
        },
        json={"available_quantity": task["quantity"]},
    )
    assert response.status_code == 200
    first = datetime.fromisoformat(response.json()["effect_at"])
    assert publish_once(engine)
    with engine.begin() as conn:
        found = rows(conn, "SELECT * FROM publication_measurements")
        assert len(found) == 1 and found[0]["effect_at"] == first
        assert rows(conn, "SELECT count(*) AS n FROM sim_publication_effects")[0]["n"] == 1


@pytest.mark.integration
def test_pending_unknown_and_stores_without_samples_are_not_successes(engine, feed_server):
    setup_world(engine, feed_server, count=2)
    assert publish_once(engine)
    with engine.begin() as conn:
        execute(
            conn,
            "UPDATE publication_measurements SET effect_at=NULL WHERE confirmed_at IS NOT NULL",
        )
        execute(conn, "INSERT INTO stores(id) VALUES ('EMPTY')")
        found = {
            s["store_id"]: s
            for s in metrics.publications(
                conn, datetime.now(UTC) - timedelta(days=1), datetime.now(UTC)
            )
        }
    assert found["T1"]["pending"] == 1
    assert found["T1"]["unknown_duration"] == 1
    assert found["T1"]["samples"] == 0 and found["T1"]["p95_seconds"] is None
    assert found["EMPTY"]["p99_seconds"] is None


@pytest.mark.integration
def test_new_cut_of_zero_has_its_own_origin_and_revision(engine, feed_server):
    provider = setup_world(engine, feed_server)
    drain(engine)
    feed_server["write"]({**feed_server["stock"], "A000": 0})
    assert services.ingest(engine, provider)["status"] == "accepted"
    services.compare_once(engine)
    drain(engine)
    link = services.status(engine)[0]
    services.cut_link(engine, link["id"])
    drain(engine)
    with engine.begin() as conn:
        samples = rows(conn, "SELECT * FROM publication_measurements ORDER BY revision")
    assert len(samples) == 3
    assert samples[-1]["origin_at"] > samples[-2]["effect_at"]
    assert samples[-1]["effect_at"] >= samples[-1]["origin_at"]


@pytest.mark.integration
def test_review_and_retries_keep_the_accepted_origin_of_the_latest_revision(engine, feed_server):
    provider = setup_world(engine, feed_server)
    admin("/admin/fault", {"store": "T1", "item": "I0", "status": 404, "remaining": 1})
    assert publish_once(engine)
    assert services.status(engine)[0]["state"] == "error"
    feed_server["write"]({**feed_server["stock"], "A000": 12})
    accepted = services.ingest(engine, provider)
    services.compare_once(engine)
    with engine.begin() as conn:
        pending = rows(conn, "SELECT * FROM publication_measurements ORDER BY revision")
        assert pending[0]["superseded_at"] is not None
        origin = pending[-1]["origin_at"]
        assert (
            origin
            == rows(conn, "SELECT finished_at FROM runs WHERE id=:id", id=accepted["id"])[0][
                "finished_at"
            ]
        )
    link = services.status(engine)[0]
    services.resume(engine, link["id"])
    drain(engine)
    with engine.begin() as conn:
        latest = rows(
            conn, "SELECT * FROM publication_measurements ORDER BY revision DESC LIMIT 1"
        )[0]
    assert latest["origin_at"] == origin and latest["effect_at"] is not None


@pytest.mark.integration
def test_the_same_authenticated_metrics_contract_is_available_in_both_services(api, engine):
    from ivostock.metrics_service import app

    independent = TestClient(app)
    independent.headers.update(api.headers)
    for path in ("/metrics/current", "/metrics/history", "/metrics/summary"):
        assert independent.get(path).status_code == 200
        assert api.get(path).status_code == 200
    assert independent.get("/openapi.json").status_code == 200
    assert independent.get("/auth/me").json() == api.get("/auth/me").json()
    paths = independent.get("/openapi.json").json()["paths"]
    assert "/auth/login" not in paths and "/auth/logout" not in paths
    with engine.begin() as conn:
        assert rows(conn, "SELECT count(*) AS n FROM metric_samples")[0]["n"] == 0
    assert api.post("/auth/logout").status_code == 200
    assert independent.get("/metrics/current").status_code == 401
    assert independent.get("/auth/me").status_code == 401
