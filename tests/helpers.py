"""Utilidades compartidas por las pruebas de integración de la API."""

import time

import httpx

from ivostock import services
from ivostock.config import Settings
from ivostock.db import rows
from ivostock.publisher import publish_once


def admin(path, payload=None):
    """Llama a la API administrativa del simulador (ensayo; la aplicación no la usa)."""
    cfg = Settings.from_env()
    headers = {"Authorization": "Bearer " + cfg.simulator_admin_token}
    response = (
        httpx.get(cfg.simulator_url + path, headers=headers)
        if payload is None
        else httpx.post(cfg.simulator_url + path, json=payload, headers=headers)
    )
    response.raise_for_status()
    return response.json()


def seed(store, count, quantity=0):
    items = [
        {"id": f"I{n}", "sku": f"A{n:03}", "available_quantity": quantity} for n in range(count)
    ]
    admin("/admin/seed", {"store": store, "items": items})


def import_catalogs(engine):
    while services.import_page(engine):
        pass


def drain(engine):
    deadline = time.monotonic() + 15
    while services.status(engine, "tasks"):
        assert time.monotonic() < deadline, services.status(engine, "tasks")
        if not publish_once(engine):
            time.sleep(0.05)


def create_provider(api, feed_server, name="Proveedor"):
    response = api.post("/providers", json={"name": name, "url": feed_server["url"]})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def links(engine):
    with engine.begin() as conn:
        return rows(conn, "SELECT * FROM links ORDER BY id")
