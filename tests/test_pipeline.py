import concurrent.futures
import os
import subprocess
import sys
import threading
import time

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from ivostock import services
from ivostock.config import Settings
from ivostock.db import database, execute, ownership, rows
from ivostock.publisher import publish_once
from ivostock.quota import reserve

pytestmark = pytest.mark.integration


def admin(path, payload=None):
    cfg = Settings.from_env()
    headers = {"Authorization": "Bearer " + cfg.simulator_admin_token}
    response = (
        httpx.get(cfg.simulator_url + path, headers=headers)
        if payload is None
        else httpx.post(cfg.simulator_url + path, json=payload, headers=headers)
    )
    response.raise_for_status()
    return response.json()


def setup_world(engine, feed_server, count=1):
    provider = services.add_provider(engine, "Proveedor", feed_server["url"])["id"]
    run = services.ingest(engine, provider)
    assert run["status"] == "accepted"
    admin(
        "/admin/seed",
        {
            "store": "T1",
            "items": [
                {"id": f"I{n}", "sku": f"A{n:03}", "available_quantity": 0} for n in range(count)
            ],
        },
    )
    services.add_store(engine, "T1")
    services.approve(engine, provider, "T1")
    services.compare_once(engine)
    return provider


def drain(engine):
    deadline = time.monotonic() + 15
    while services.status(engine, "tasks"):
        assert time.monotonic() < deadline, services.status(engine, "tasks")
        if not publish_once(engine):
            time.sleep(0.05)


def test_real_http_pipeline_idempotence_and_immutable_snapshot(engine, feed_server):
    provider = setup_world(engine, feed_server)
    drain(engine)
    first = services.status(engine, "runs")[0]
    services.ingest(engine, provider, replay_of=first["id"])
    services.compare_once(engine)
    assert services.status(engine, "tasks") == []
    assert admin("/admin/stores/T1")[0]["writes"] == 1
    assert services.status(engine)[0]["confirmed"] == 10
    from ivostock.storage import Snapshots

    assert Snapshots().get(first["snapshot_key"]) == feed_server["path"].read_bytes()


def test_quarantine_freezes_and_missing_becomes_zero(engine, feed_server):
    provider = setup_world(engine, feed_server)
    drain(engine)
    feed_server["write"]({})
    assert services.ingest(engine, provider)["status"] == "quarantined"
    services.compare_once(engine)
    assert services.status(engine, "tasks") == []
    stock = dict(feed_server["stock"])
    del stock["A000"]  # 2% de D: no supera el umbral.
    feed_server["write"](stock)
    assert services.ingest(engine, provider)["status"] == "accepted"
    services.compare_once(engine)
    drain(engine)
    assert admin("/admin/stores/T1")[0]["status"] == "out_of_stock"


def test_replacement_preserves_fifo_and_cut_survives_ingestion(engine, feed_server):
    provider = setup_world(engine, feed_server)
    initial = services.status(engine, "tasks")[0]
    stock = {**feed_server["stock"], "A000": 15}
    feed_server["write"](stock)
    services.ingest(engine, provider)
    services.compare_once(engine)
    task = services.status(engine, "tasks")[0]
    assert task["quantity"] == 15 and task["enqueued_at"] == initial["enqueued_at"]
    assert task["replacements"] == 1
    services.cut(engine, provider, 1)
    services.ingest(engine, provider)
    services.compare_once(engine)
    drain(engine)
    assert services.status(engine)[0]["state"] == "inactive"
    assert admin("/admin/stores/T1")[0]["available_quantity"] == 0


def test_dead_letter_requires_manual_resume_with_current_quantity(engine, feed_server):
    provider = setup_world(engine, feed_server)
    admin("/admin/fault", {"store": "T1", "status": 404, "remaining": 1})
    assert publish_once(engine)
    assert services.status(engine)[0]["state"] == "error"
    feed_server["write"]({**feed_server["stock"], "A000": 18})
    services.ingest(engine, provider)
    services.compare_once(engine)
    assert services.status(engine, "tasks") == []
    services.resume(engine, 1)
    drain(engine)
    assert admin("/admin/stores/T1")[0]["available_quantity"] == 18
    assert services.status(engine, "deadletters")[0]["quantity"] == 10
    assert services.status(engine, "deadletters")[0]["reviewed_at"] is not None


def test_429_never_spends_retry_budget_or_creates_dead_letter(engine, feed_server):
    setup_world(engine, feed_server)
    admin("/admin/fault", {"store": "T1", "status": 429, "remaining": 1})
    publish_once(engine)
    assert services.status(engine, "tasks")[0]["attempts"] == 0
    assert services.status(engine, "deadletters") == []
    drain(engine)


def test_backoff_allows_other_ready_work_and_exhaustion_is_explicit(engine, feed_server):
    setup_world(engine, feed_server, count=2)
    admin("/admin/fault", {"store": "T1", "item": "I0", "status": 503, "remaining": -1})
    publish_once(engine)
    assert publish_once(engine)  # I1 sigue disponible mientras I0 espera.
    assert admin("/admin/stores/T1")[1]["available_quantity"] == 10
    for _ in range(4):
        with engine.begin() as conn:
            execute(conn, "UPDATE tasks SET available_at=now()")
        publish_once(engine)
    assert len(services.status(engine, "deadletters")) == 1


def test_quota_is_atomic_shared_and_survives_new_engine(engine):
    def request(_):
        return reserve(engine, "T1")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(request, range(80)))
    assert sum(delay == 0 for delay in outcomes) == 60
    engine.dispose()
    assert reserve(database(), "T1") > 0
    assert reserve(database(), "T2") == 0


def test_simulator_counts_reads_writes_and_failed_calls(engine, feed_server):
    setup_world(engine, feed_server)
    cfg = Settings.from_env()
    with engine.begin() as conn:
        execute(conn, "DELETE FROM sim_calls")
    with httpx.Client(headers={"Authorization": "Bearer " + cfg.simulator_token}) as client:
        for n in range(60):
            response = (
                client.get(cfg.simulator_url + "/stores/T1/items")
                if n % 2
                else client.put(
                    cfg.simulator_url + "/stores/T1/items/missing/stock",
                    json={"available_quantity": 1},
                )
            )
            assert response.status_code in (200, 404)
        assert client.get(cfg.simulator_url + "/stores/T1/items").status_code == 429


def test_schedule_and_ownership(engine, feed_server):
    provider = services.add_provider(engine, "P", feed_server["url"])["id"]
    assert services.ingest(engine, provider, scheduled=True)["status"] == "accepted"
    with engine.begin() as conn:
        before = rows(conn, "SELECT next_run_at FROM providers WHERE id=:p", p=provider)[0][
            "next_run_at"
        ]
    services.ingest(engine, provider)
    assert services.ingest(engine, provider, scheduled=True)["status"] == "not_due"
    with engine.begin() as conn:
        assert (
            rows(conn, "SELECT next_run_at FROM providers WHERE id=:p", p=provider)[0][
                "next_run_at"
            ]
            == before
        )
    with ownership(engine, f"provider:{provider}"):
        assert services.ingest(engine, provider)["status"] == "busy"


def test_simulator_counts_invalid_payload_and_auth_failures(engine, feed_server):
    setup_world(engine, feed_server)
    cfg = Settings.from_env()
    with engine.begin() as conn:
        execute(conn, "DELETE FROM sim_calls")
    with httpx.Client() as client:
        assert client.get(cfg.simulator_url + "/stores/T1/items").status_code == 401
        headers = {"Authorization": "Bearer " + cfg.simulator_token}
        assert (
            client.put(
                cfg.simulator_url + "/stores/T1/items/I0/stock",
                headers=headers,
                json={"available_quantity": -1},
            ).status_code
            == 422
        )
    with engine.begin() as conn:
        assert rows(conn, "SELECT count(*) AS n FROM sim_calls WHERE store_id='T1'")[0]["n"] == 2


def test_single_writer_constraint(engine, feed_server):
    setup_world(engine, feed_server)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        execute(
            conn,
            "INSERT INTO links(provider_id,store_id,item_id,sku,desired,confirmed) SELECT provider_id,store_id,item_id,sku,desired,confirmed FROM links",
        )


def test_late_ack_keeps_new_cut_revision(engine, feed_server, monkeypatch):
    provider = setup_world(engine, feed_server)
    responded, release = threading.Event(), threading.Event()
    errors = []

    def checkpoint(point):
        if point == "marketplace_responded":
            responded.set()
            assert release.wait(10)

    def publishing():
        try:
            publish_once(engine)
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr("ivostock.publisher.checkpoint", checkpoint)
    thread = threading.Thread(target=publishing)
    thread.start()
    try:
        assert responded.wait(10)
        services.cut(engine, provider, 1)
        services.ingest(engine, provider)
        services.compare_once(engine)
    finally:
        release.set()
        thread.join(timeout=10)
    assert not errors
    assert services.status(engine, "tasks")[0]["quantity"] == 0
    assert services.status(engine)[0]["state"] == "active"
    drain(engine)
    assert services.status(engine)[0]["state"] == "inactive"
    assert admin("/admin/stores/T1")[0]["available_quantity"] == 0


def test_failed_cut_stays_zero_when_manually_resumed(engine, feed_server):
    provider = setup_world(engine, feed_server)
    drain(engine)
    services.cut(engine, provider, 1)
    admin("/admin/fault", {"store": "T1", "status": 404, "remaining": 1})
    publish_once(engine)
    assert services.status(engine)[0]["state"] == "error"
    services.ingest(engine, provider)
    services.compare_once(engine)
    services.resume(engine, 1)
    drain(engine)
    assert services.status(engine)[0]["state"] == "inactive"
    assert services.status(engine, "deadletters")[0]["quantity"] == 0


POINTS = [
    ("snapshot_stored", "ingest"),
    ("state_in_transaction", "ingest"),
    ("accepted_committed", "ingest"),
    ("comparison_claimed", "compare"),
    ("enqueued_in_transaction", "compare"),
    ("comparison_committed", "compare"),
    ("task_claimed", "publish"),
    ("marketplace_responded", "publish"),
    ("ack_in_transaction", "publish"),
    ("cut_committed", "off"),
]


@pytest.mark.parametrize("point,command", POINTS)
def test_abrupt_process_crash_keeps_current_work(engine, feed_server, tmp_path, point, command):
    provider = setup_world(engine, feed_server)
    drain(engine)
    feed_server["write"]({**feed_server["stock"], "A000": 12})
    if command not in ("ingest", "off"):
        services.ingest(engine, provider)
    if command == "publish":
        services.compare_once(engine)
    marker = tmp_path / "crash-marker"
    env = {**os.environ, "IVO_FAILPOINT": point, "IVO_FAILPOINT_MARKER": str(marker)}
    argv = [sys.executable, "-m", "ivostock.cli", command]
    if command in ("ingest", "off"):
        argv.append("1")
    proc = subprocess.Popen(argv, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    started = time.monotonic()
    try:
        while not marker.exists() and time.monotonic() - started < 15:
            if proc.poll() is not None:
                pytest.fail(proc.stderr.read().decode())
            time.sleep(0.02)
        assert marker.exists(), point
    finally:
        proc.kill()
        proc.wait(timeout=5)
        proc.stderr.close()
    recovered = time.monotonic()
    services.ingest(engine, provider)
    services.compare_once(engine)
    drain(engine)
    link = services.status(engine)[0]
    expected = 0 if command == "off" else 12
    assert link["confirmed"] == link["desired"] == expected
    assert admin("/admin/stores/T1")[0]["available_quantity"] == expected
    assert services.status(engine, "deadletters") == []
    assert time.monotonic() - recovered < 600
