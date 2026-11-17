"""Aprovisionamiento de tiendas fuera de la app (C1) y tiendas configuradas (C2)."""

import importlib.util
from pathlib import Path

import pytest

from ivostock import provision
from ivostock.config import Settings, parse_stores
from tests.helpers import admin

ROOT = Path(__file__).resolve().parents[1]
SKUS = [f"A{n:03}" for n in range(200)]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Sin base de datos ---------------------------------------------------------------------


def test_samples_are_distinct_overlapping_and_deterministic():
    samples = provision.store_samples(SKUS, ["T1", "T2"])
    t1, t2 = set(samples["T1"]), set(samples["T2"])
    assert len(t1) == len(t2) == 100
    assert t1 != t2 and len(t1 & t2) == 50 and len(t1 | t2) == 150
    assert t1 <= set(SKUS) and t2 <= set(SKUS)
    assert samples == provision.store_samples(list(reversed(SKUS)), ["T1", "T2"])


def test_adding_a_store_at_the_end_keeps_the_previous_samples():
    two = provision.store_samples(SKUS, ["T1", "T2"])
    three = provision.store_samples(SKUS, ["T1", "T2", "T3"])
    assert {s: three[s] for s in ("T1", "T2")} == two
    assert set(three["T3"]) & set(two["T1"]) & set(two["T2"]) and three["T3"] != two["T1"]


@pytest.mark.parametrize(
    ("skus", "stores", "fraction", "shared"),
    [
        (SKUS[:2], ["T1", "T2"], 0.5, 0.5),  # inventario demasiado chico
        (SKUS, ["T1", "T2"], 0.5, 0.0),  # sin núcleo común: no se solaparían
        (SKUS, ["T1", "T2"], 0.5, 1.0),  # sin SKU propios: serían idénticas
        (SKUS, ["T1", "T2", "T3", "T4"], 0.5, 0.5),  # no alcanza para tantas tiendas
        (SKUS, ["T1"], 0, 0.5),
        (SKUS, ["T1"], 0.5, 1.5),
    ],
)
def test_impossible_samples_fail_loudly(skus, stores, fraction, shared):
    with pytest.raises(ValueError):
        provision.store_samples(skus, stores, fraction, shared)


def test_a_single_store_needs_no_overlap():
    assert len(provision.store_samples(SKUS, ["T1"], 0.5, 0.0)["T1"]) == 100


def test_catalog_items_have_own_ids_and_zero_stock():
    items = provision.catalog_items(["B", "A", "C"])
    assert [i["id"] for i in items] == ["ITEM000001", "ITEM000002", "ITEM000003"]
    assert [i["sku"] for i in items] == ["A", "B", "C"]
    assert {i["available_quantity"] for i in items} == {0}


def test_missing_inventory_is_reported_before_touching_the_marketplace(tmp_path):
    with pytest.raises(ValueError, match="No existe el inventario"):
        provision.provision_stores(tmp_path / "falta.csv", ["T1"])


def test_script_reports_configuration_errors_without_a_traceback(tmp_path, monkeypatch):
    script = load_script("provisionar_tiendas")
    monkeypatch.setattr("sys.argv", ["x", "--feed", str(tmp_path / "falta.csv")])
    with pytest.raises(SystemExit) as stop:
        script.main()
    assert "No existe el inventario" in str(stop.value)
    monkeypatch.setattr("sys.argv", ["x", "--stores", "T1,T1", "--feed", str(tmp_path / "f.csv")])
    with pytest.raises(SystemExit, match="MARKETPLACE_STORES mal formado"):
        script.main()


def test_stores_setting_is_parsed_and_validated(monkeypatch):
    assert parse_stores(" T1, T2 ") == ("T1", "T2")
    assert parse_stores("") == parse_stores(None) == ()
    for bad in ("T1,T1", "T 1", "../x", "T1;T2", "x" * 33):
        with pytest.raises(ValueError, match="MARKETPLACE_STORES"):
            parse_stores(bad)
    for key in ("DATABASE_URL", "S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
        monkeypatch.setenv(key, "x")
    monkeypatch.setenv("SIMULATOR_TOKEN", "x")
    monkeypatch.setenv("SIMULATOR_ADMIN_TOKEN", "x")
    monkeypatch.setenv("MARKETPLACE_STORES", "T1,T2")
    assert Settings.from_env().marketplace_stores == ("T1", "T2")
    monkeypatch.delenv("MARKETPLACE_STORES")
    assert Settings.from_env().marketplace_stores == ()


def test_configurar_declares_the_available_stores(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    load_script("configurar").main()
    assert "MARKETPLACE_STORES=T1,T2\n" in (tmp_path / ".env").read_text(encoding="utf-8")


# --- Con el simulador ----------------------------------------------------------------------


@pytest.mark.integration
def test_provisioning_creates_each_missing_store_once(engine, feed_server):
    feed_server["write"]({f"A{n:03}": n for n in range(50)})
    first = provision.provision_stores(feed_server["path"], ["T1", "T2"])
    assert first == {
        "T1": {"status": "created", "items": 25},
        "T2": {"status": "created", "items": 25},
    }
    items = {store: admin(f"/admin/stores/{store}") for store in ("T1", "T2")}
    assert {len(v) for v in items.values()} == {25}
    assert [i["id"] for i in items["T1"][:2]] == ["ITEM000001", "ITEM000002"]
    assert {i["available_quantity"] for v in items.values() for i in v} == {0}
    skus = {store: {i["sku"] for i in v} for store, v in items.items()}
    assert skus["T1"] != skus["T2"] and len(skus["T1"] & skus["T2"]) == 12
    again = provision.provision_stores(feed_server["path"], ["T1", "T2"])
    assert {v["status"] for v in again.values()} == {"exists"}
    assert admin("/admin/stores/T1/summary")["items"] == 25


@pytest.mark.integration
def test_provisioning_a_missing_store_later_gives_the_same_sample(engine, feed_server):
    feed_server["write"]({f"A{n:03}": n for n in range(50)})
    provision.provision_stores(feed_server["path"], ["T1", "T2"])
    before = {i["sku"] for i in admin("/admin/stores/T2")}
    from ivostock.db import execute

    with engine.begin() as conn:
        execute(conn, "DELETE FROM sim_items WHERE store_id='T2'")
        execute(conn, "DELETE FROM sim_stores WHERE id='T2'")
    result = provision.provision_stores(feed_server["path"], ["T1", "T2"])
    assert (result["T1"]["status"], result["T2"]["status"]) == ("exists", "created")
    assert {i["sku"] for i in admin("/admin/stores/T2")} == before
