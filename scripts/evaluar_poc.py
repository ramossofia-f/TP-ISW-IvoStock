"""Ensayo local con datos reales, API detenida y PostgreSQL interrumpido."""

import argparse
import functools
import http.server
import json
import os
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ivostock import services
from ivostock.config import Settings
from ivostock.db import database
from ivostock.feed import parse, prepare
from ivostock.logs import configurar
from ivostock.publisher import publish_once


def compose(*args):
    subprocess.run(["docker", "compose", *args], check=True, stdout=subprocess.DEVNULL)


def automatic_recovery(engine, provider, identifier):
    """Contenedor de ensayo propio que termina sin cleanup después de confirmar un cero."""
    link = next(link for link in services.status(engine) if link["provider_id"] == provider)
    services.cut(engine, provider, link["id"])
    postgres = subprocess.check_output(
        ["docker", "compose", "ps", "-q", "postgres"], text=True
    ).strip()
    networks = json.loads(
        subprocess.check_output(
            ["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", postgres], text=True
        )
    )
    image = subprocess.check_output(
        ["docker", "compose", "images", "-q", "publish"], text=True
    ).strip()
    name = f"e2-recovery-{identifier}"
    started = time.monotonic()
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--restart",
            "on-failure",
            "--env-file",
            ".env",
            "--network",
            next(iter(networks)),
            "-e",
            "IVO_FAILPOINT=ack_committed",
            "-e",
            "IVO_FAILPOINT_MODE=exit",
            image,
            "python",
            "-m",
            "ivostock.worker",
            "publish",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    try:
        deadline = started + 60
        while time.monotonic() < deadline:
            count = int(
                subprocess.check_output(
                    ["docker", "inspect", "-f", "{{.RestartCount}}", name], text=True
                )
            )
            state = json.loads(
                subprocess.check_output(
                    ["docker", "inspect", "-f", "{{json .State}}", name], text=True
                )
            )
            restarted_at = datetime.fromisoformat(state["StartedAt"].replace("Z", "+00:00"))
            with engine.begin() as conn:
                from ivostock.db import rows

                heartbeat = rows(conn, "SELECT at FROM worker_heartbeats WHERE name='publish'")
            current = next(item for item in services.status(engine) if item["id"] == link["id"])
            if (
                count > 0
                and state["Running"]
                and heartbeat
                and heartbeat[0]["at"] >= restarted_at
                and current["state"] == "inactive"
            ):
                return {"seconds": round(time.monotonic() - started, 3), "restart_count": count}
            time.sleep(0.2)
        raise RuntimeError("No se observó recuperación automática")
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=True, stdout=subprocess.DEVNULL)


def setup_environment():
    configurar()
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key] = value
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace("@postgres:", "@127.0.0.1:")
    os.environ["S3_ENDPOINT"] = "http://127.0.0.1:9000"
    os.environ["SIMULATOR_URL"] = "http://127.0.0.1:8001"


def control(path, payload=None):
    cfg = Settings.from_env()
    headers = {"Authorization": "Bearer " + cfg.simulator_admin_token}
    with httpx.Client(timeout=30) as client:
        response = (
            client.get(cfg.simulator_url + path, headers=headers)
            if payload is None
            else client.post(cfg.simulator_url + path, json=payload, headers=headers)
        )
    response.raise_for_status()
    return response.json()


def drain(engine, provider):
    deadline = time.monotonic() + 180
    while any(
        link["pending_quantity"] is not None
        for link in services.status(engine)
        if link["provider_id"] == provider
    ):
        if time.monotonic() >= deadline:
            raise RuntimeError("El ensayo no drenó en tres minutos")
        if not publish_once(engine):
            time.sleep(0.1)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--captured-at", required=True)
    args = ap.parse_args()
    setup_environment()
    identifier = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    directory = Path("data/feeds")
    manifest = prepare(args.source, directory, "Celesa; snapshot real archivado", args.captured_at)
    raw = (directory / manifest["file"]).read_bytes()
    stock = parse(raw).stock
    live = directory / f"ensayo-{identifier}.csv"
    live.write_bytes(raw)
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {
        "executed_at": datetime.now(UTC).isoformat(),
        "source": manifest,
        "synthetic_variants": True,
        "store": f"E2-{identifier}",
    }
    compose("stop", "ingest", "compare", "publish", "api")
    try:
        engine = database()
        provider = services.add_provider(
            engine, f"E2-{identifier}", f"http://127.0.0.1:{server.server_port}/{live.name}"
        )["id"]
        start = time.monotonic()
        accepted = services.ingest(engine, provider)
        assert accepted["status"] == "accepted"
        services.compare_once(engine)
        report["full_ingestion_seconds"] = round(time.monotonic() - start, 3)
        items = [
            {"id": f"ITEM{n:06}", "sku": sku, "available_quantity": quantity}
            for n, (sku, quantity) in enumerate(sorted(stock.items())[:1000], 1)
        ]
        control("/admin/seed", {"store": report["store"], "items": items})
        services.add_store(engine, report["store"])
        services.approve(engine, provider, report["store"], [i["id"] for i in items[:10]])
        services.compare_once(engine)
        assert not [
            link
            for link in services.status(engine)
            if link["provider_id"] == provider and link["pending_quantity"] is not None
        ]
        report["static_catalog_items"] = len(items)
        report["active_links"] = 10
        varied = {**stock, items[0]["sku"]: stock[items[0]["sku"]] + 1}
        live.write_text(
            "SKU;stock\n" + "".join(f"{sku};{q}\n" for sku, q in varied.items()), encoding="utf-8"
        )
        services.ingest(engine, provider)
        services.compare_once(engine)
        drain(engine, provider)
        observed = control(f"/admin/stores/{report['store']}")
        assert observed[0]["available_quantity"] == varied[items[0]["sku"]]
        report["api_stopped_propagation"] = True
        writes = sum(i["writes"] for i in observed)
        services.ingest(engine, provider)
        services.compare_once(engine)
        drain(engine, provider)
        assert sum(i["writes"] for i in control(f"/admin/stores/{report['store']}")) == writes
        report["stable_replay_additional_writes"] = 0
        live.write_text("SKU;stock\n", encoding="utf-8")
        assert services.ingest(engine, provider)["status"] == "quarantined"
        report["truncation_quarantined"] = True
        live.write_bytes(raw)
        services.ingest(engine, provider)
        services.compare_once(engine)
        control(
            "/admin/fault",
            {"store": report["store"], "item": items[0]["id"], "status": 404, "remaining": 1},
        )
        publish_once(engine)
        failures = [
            d
            for d in services.status(engine, "deadletters")
            if d["link_id"]
            in {link["id"] for link in services.status(engine) if link["provider_id"] == provider}
        ]
        assert failures
        services.resume(engine, failures[0]["link_id"])
        drain(engine, provider)
        report["dead_letter_reviewed"] = True
        report["automatic_process_recovery"] = automatic_recovery(engine, provider, identifier)
        services.cut(engine, provider)
        pending_before = [
            link for link in services.status(engine) if link["provider_id"] == provider
        ]
        assert all(link["cut_requested"] for link in pending_before)
        engine.dispose()
        restart = time.monotonic()
        compose("kill", "-s", "SIGKILL", "postgres")
        compose("up", "-d", "--wait", "postgres")
        drain(engine, provider)
        report["postgres_recovery_seconds"] = round(time.monotonic() - restart, 3)
        after = [link for link in services.status(engine) if link["provider_id"] == provider]
        assert all(link["state"] == "inactive" and link["confirmed"] == 0 for link in after)
        observed = control(f"/admin/stores/{report['store']}")
        assert all(i["available_quantity"] == 0 for i in observed[:10])
        report["persisted_cuts_applied"] = len(after)
        report["current_work_lost"] = 0
        assert report["full_ingestion_seconds"] < 600
        assert report["postgres_recovery_seconds"] < 600
        target = Path("data/evidencia/poc.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        compose("start", "api", "ingest", "compare", "publish")


if __name__ == "__main__":
    main()
