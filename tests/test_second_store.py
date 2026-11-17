"""Segunda tienda reutilizando el inventario (C2..C7) y criterio de aceptación 6.

Las tiendas se crean aparte con `provision` (como en producción, donde ya existirían); la
aplicación sólo las incorpora, siempre por su API, sin modificar código ni configuración.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from ivostock import cli, provision, quota, services
from ivostock.config import Settings
from ivostock.db import execute, rows
from tests.helpers import admin, create_provider, drain, import_catalogs, links, seed

pytestmark = pytest.mark.integration

STOCK = {f"A{n:03}": n + 1 for n in range(50)}


@pytest.fixture
def samples(engine, feed_server):
    """T1 y T2 aprovisionadas aparte desde el inventario del proveedor."""
    feed_server["write"](STOCK)
    provision.provision_stores(feed_server["path"], ["T1", "T2"])
    return provision.store_samples(sorted(STOCK), ["T1", "T2"])


def quantities(store):
    return {i["sku"]: i["available_quantity"] for i in admin(f"/admin/stores/{store}")}


def snapshot(engine, store):
    """Todo lo observable de una tienda: vínculos, intentos de publicación y escrituras."""
    with engine.begin() as conn:
        mine = rows(
            conn,
            "SELECT id,item_id,sku,state,desired,confirmed,revision,last_success_at,cut_requested"
            " FROM links WHERE store_id=:s ORDER BY id",
            s=store,
        )
        attempts = rows(
            conn,
            "SELECT count(*) AS n FROM attempts a JOIN links l ON l.id=a.link_id WHERE l.store_id=:s",
            s=store,
        )[0]["n"]
    writes = sum(i["writes"] for i in admin(f"/admin/stores/{store}"))
    return {"links": [dict(r) for r in mine], "attempts": attempts, "writes": writes}


def operate_t1(api, engine, feed_server):
    """Operación normal de la primera tienda: incorporar, ingerir, vincular y sincronizar."""
    assert api.post("/stores", json={"store": "T1"}).status_code == 201
    import_catalogs(engine)
    provider = create_provider(api, feed_server)
    assert services.ingest(engine, provider)["status"] == "accepted"
    approved = api.post(f"/providers/{provider}/approve", json={"store": "T1", "all": True})
    assert approved.json() == {"approved": 25, "awaiting_ingest": False}
    services.compare_once(engine)
    drain(engine)
    return provider


def incorporate_t2(api, engine, provider, synchronize=True):
    assert api.post("/stores", json={"store": "T2"}).status_code == 201
    import_catalogs(engine)
    approved = api.post(f"/providers/{provider}/approve", json={"store": "T2", "all": True})
    assert approved.json() == {"approved": 25, "awaiting_ingest": False}
    services.compare_once(engine)
    if synchronize:
        drain(engine)


def run(*argv):
    return cli.execute(cli.parser().parse_args(list(argv)))


def processed(engine):
    with engine.begin() as conn:
        return {
            r["id"]: r["import_offset"] for r in rows(conn, "SELECT id,import_offset FROM stores")
        }


def import_order(engine, calls):
    """Qué tienda avanzó en cada llamada a `import_page`."""
    order = []
    for _ in range(calls):
        before = processed(engine)
        assert services.import_page(engine)
        after = processed(engine)
        moved = [store for store in after if after[store] != before[store]]
        assert len(moved) == 1, (before, after)
        order.append(moved[0])
    return order


# --- C2: la app sólo incorpora tiendas existentes ------------------------------------------


def test_the_app_never_creates_stores_in_the_marketplace(api, engine, samples):
    unprovisioned = api.post("/stores", json={"store": "T3"})
    assert unprovisioned.status_code == 404
    assert admin("/admin/stores/T3/summary")["exists"] is False
    with engine.begin() as conn:
        assert rows(conn, "SELECT count(*) AS n FROM market_calls WHERE store_id='T3'")[0]["n"] == 1
    assert api.get("/stores").json() == []


def test_unlisted_stores_are_rejected_without_calling_the_marketplace(api, engine, samples):
    response = api.post("/stores", json={"store": "T9"})
    assert response.json() == {"detail": "La tienda no está disponible para incorporar"}
    with engine.begin() as conn:
        assert rows(conn, "SELECT count(*) AS n FROM market_calls")[0]["n"] == 0


def test_cli_store_add_only_registers_existing_stores(engine, samples):
    assert run("store-add", "T9") == (
        False,
        {"error": "La tienda no está disponible para incorporar"},
    )
    assert run("store-add", "T3") == (False, {"error": "La tienda no existe en el marketplace"})
    assert admin("/admin/stores/T3/summary")["exists"] is False
    ok, result = run("store-add", "T1")
    assert ok and result["status"] == "importing"
    assert run("store-add", "T1", "--wait") == (True, {"store": "T1", "items": 25})


def test_a_store_that_disappears_is_reported_clearly_and_does_not_block_the_others(
    api, engine, samples
):
    for store in ("T1", "T2"):
        assert api.post("/stores", json={"store": store}).status_code == 201
    with engine.begin() as conn:
        execute(conn, "DELETE FROM sim_items WHERE store_id='T1'")
        execute(conn, "DELETE FROM sim_stores WHERE id='T1'")
    assert services.import_page(engine) is True  # el 404 se registra sin lanzar excepción
    import_catalogs(engine)
    t1, t2 = api.get("/stores").json()
    assert (t1["status"], t1["last_error"]) == ("degraded", "La tienda no existe en el marketplace")
    assert t1["catalog_imported"] is False
    assert t2["catalog_imported"] is True and t2["processed"] == 25
    with engine.begin() as conn:
        wait = rows(conn, "SELECT blocked_until>now() AS blocked FROM stores WHERE id='T1'")
    assert wait[0]["blocked"] is True


# --- C3: rotación entre tiendas ------------------------------------------------------------


def test_catalog_import_alternates_between_stores(api, engine):
    seed("T1", 350)
    seed("T2", 350)
    for store in ("T1", "T2"):
        api.post("/stores", json={"store": store})
    assert import_order(engine, 8) == ["T1", "T2"] * 4
    assert processed(engine) == {"T1": 350, "T2": 350}
    assert [s["catalog_imported"] for s in api.get("/stores").json()] == [True, True]


def test_a_small_new_store_is_not_starved_by_a_long_import(api, engine):
    seed("T1", 1000)
    api.post("/stores", json={"store": "T1"})
    assert import_order(engine, 3) == ["T1"] * 3
    seed("T2", 150)
    api.post("/stores", json={"store": "T2"})
    assert import_order(engine, 3) == ["T2", "T1", "T2"]
    t1, t2 = api.get("/stores").json()
    assert t2["catalog_imported"] is True and t2["processed"] == 150
    assert t1["catalog_imported"] is False and t1["processed"] == 400


def test_two_simultaneous_imports_take_different_stores(api, engine):
    seed("T1", 350)
    seed("T2", 350)
    for store in ("T1", "T2"):
        api.post("/stores", json={"store": store})
    start = threading.Barrier(2)

    def one_page():
        start.wait()
        return services.import_page(engine)

    with ThreadPoolExecutor(2) as pool:
        results = [f.result(timeout=30) for f in [pool.submit(one_page), pool.submit(one_page)]]
    assert results == [True, True]
    assert processed(engine) == {"T1": 100, "T2": 100}


def test_a_store_without_quota_yields_its_turn_instead_of_blocking_the_others(api, engine):
    seed("T1", 350)
    seed("T2", 350)
    for store in ("T1", "T2"):
        api.post("/stores", json={"store": store})
    with engine.begin() as conn:
        execute(conn, "INSERT INTO market_calls(store_id) SELECT 'T1' FROM generate_series(1,60)")
    started = time.monotonic()
    assert import_order(engine, 2) == ["T2", "T2"]
    assert time.monotonic() - started < 5
    assert processed(engine)["T1"] == 0


# --- C4: una tienda nueva reutiliza el inventario aceptado ---------------------------------


def test_new_store_suggestions_and_approval_do_not_redownload_the_provider(
    api, engine, feed_server, samples
):
    provider = operate_t1(api, engine, feed_server)
    downloads = len(feed_server["hits"])
    runs = len(services.status(engine, "runs"))
    assert api.post("/stores", json={"store": "T2"}).status_code == 201
    import_catalogs(engine)
    found = api.get(
        f"/providers/{provider}/suggestions", params={"store": "T2", "limit": 200}
    ).json()
    assert found["total"] == 25 and {i["sku"] for i in found["items"]} == set(samples["T2"])
    assert all(i["desired"] == STOCK[i["sku"]] and i["confirmed"] == 0 for i in found["items"])
    approved = api.post(f"/providers/{provider}/approve", json={"store": "T2", "all": True})
    assert approved.json() == {"approved": 25, "awaiting_ingest": False}
    assert len(feed_server["hits"]) == downloads
    assert len(services.status(engine, "runs")) == runs


# --- C5: los vínculos de T1 no se tocan ----------------------------------------------------


def test_approving_in_the_new_store_leaves_the_first_store_untouched(
    api, engine, feed_server, samples
):
    provider = operate_t1(api, engine, feed_server)
    before = snapshot(engine, "T1")
    incorporate_t2(api, engine, provider, synchronize=False)
    with engine.begin() as conn:
        queued = rows(
            conn,
            "SELECT DISTINCT l.store_id FROM tasks t JOIN links l ON l.id=t.link_id",
        )
    assert {r["store_id"] for r in queued} == {"T2"}
    drain(engine)
    assert snapshot(engine, "T1") == before
    created = [link for link in links(engine) if link["store_id"] == "T2"]
    assert len(created) == 25
    for link in created:
        assert link["state"] == "active" and link["initial_confirmed"] == 0
        assert link["desired"] == link["confirmed"] == STOCK[link["sku"]]
    assert quantities("T2") == {sku: STOCK[sku] for sku in samples["T2"]}


# --- C6: RF-08 e INV-1 ---------------------------------------------------------------------


def test_shared_skus_get_the_full_quantity_in_each_store_with_one_writer_per_listing(
    api, engine, feed_server, samples
):
    provider = operate_t1(api, engine, feed_server)
    incorporate_t2(api, engine, provider)
    shared = set(samples["T1"]) & set(samples["T2"])
    assert len(shared) == 12
    by_store = {
        store: {link["sku"]: link for link in links(engine) if link["store_id"] == store}
        for store in ("T1", "T2")
    }
    for sku in shared:
        for store in ("T1", "T2"):
            link = by_store[store][sku]
            assert link["desired"] == link["confirmed"] == STOCK[sku]  # RF-08: no se reparte
        assert quantities("T1")[sku] == quantities("T2")[sku] == STOCK[sku]
    ids = {store: {link["item_id"] for link in by_store[store].values()} for store in by_store}
    assert "ITEM000001" in ids["T1"] & ids["T2"]  # el mismo id en tiendas distintas no choca
    with engine.begin() as conn:
        twice = rows(
            conn,
            "SELECT store_id,item_id FROM links WHERE state!='inactive'"
            " GROUP BY 1,2 HAVING count(*)>1",
        )
    assert twice == []
    other = create_provider(api, feed_server, "Otro")
    assert services.ingest(engine, other)["status"] == "accepted"
    url = f"/providers/{other}"
    assert api.get(url + "/suggestions", params={"store": "T2"}).json()["total"] == 0
    item = by_store["T2"][sorted(shared)[0]]["item_id"]
    taken = api.post(url + "/approve", json={"store": "T2", "items": [item]})
    assert taken.status_code == 409
    assert api.post(url + "/approve", json={"store": "T2", "all": True}).json()["approved"] == 0


# --- C7: cuota independiente por tienda ----------------------------------------------------


def test_client_side_quota_is_independent_per_store(engine):
    assert all(quota.reserve(engine, "T1") == 0.0 for _ in range(60))
    assert quota.reserve(engine, "T1") > 0
    assert quota.has_capacity(engine, "T1") is False
    assert quota.has_capacity(engine, "T2") is True
    assert quota.reserve(engine, "T2") == 0.0
    with engine.begin() as conn:
        counts = {
            r["store_id"]: r["n"]
            for r in rows(conn, "SELECT store_id,count(*) AS n FROM market_calls GROUP BY 1")
        }
    assert counts == {"T1": 60, "T2": 1}


def test_marketplace_side_quota_is_independent_per_store(engine, samples):
    cfg = Settings.from_env()
    headers = {"Authorization": "Bearer " + cfg.simulator_token}

    def read(store):
        url = f"{cfg.simulator_url}/stores/{store}/items"
        return httpx.get(url, params={"limit": 1}, headers=headers)

    assert [read("T1").status_code for _ in range(60)] == [200] * 60
    assert read("T1").status_code == 429
    assert read("T2").status_code == 200
    assert admin("/admin/stores/T2/summary")["calls_last_minute"] == 1
    assert admin("/admin/stores/T1/summary")["calls_last_minute"] >= 60


# --- Criterio de aceptación 6 --------------------------------------------------------------


def test_one_provider_run_updates_both_stores(api, engine, feed_server, samples):
    provider = operate_t1(api, engine, feed_server)
    incorporate_t2(api, engine, provider)
    t1_only = sorted(set(samples["T1"]) - set(samples["T2"]))[0]
    t2_only = sorted(set(samples["T2"]) - set(samples["T1"]))[0]
    both = sorted(set(samples["T1"]) & set(samples["T2"]))[0]
    downloads, runs = len(feed_server["hits"]), len(services.status(engine, "runs"))
    writes = {s: snapshot(engine, s)["writes"] for s in ("T1", "T2")}
    feed_server["write"]({**STOCK, both: 100, t1_only: 101, t2_only: 102})

    assert services.ingest(engine, provider)["status"] == "accepted"
    services.compare_once(engine)
    drain(engine)

    assert len(feed_server["hits"]) == downloads + 1
    assert len(services.status(engine, "runs")) == runs + 1
    q1, q2 = quantities("T1"), quantities("T2")
    assert (q1[both], q2[both]) == (100, 100)
    assert q1[t1_only] == 101 and q2[t2_only] == 102
    assert t2_only not in q1 and t1_only not in q2
    assert all(q1[s] == STOCK[s] for s in q1 if s not in (both, t1_only))
    assert all(q2[s] == STOCK[s] for s in q2 if s not in (both, t2_only))
    # Sólo se escribió lo que cambió en cada tienda.
    assert {s: snapshot(engine, s)["writes"] - writes[s] for s in writes} == {"T1": 2, "T2": 2}
