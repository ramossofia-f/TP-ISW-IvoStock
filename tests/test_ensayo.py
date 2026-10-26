import random
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from ivostock import cli, proveedor
from ivostock.usuario import Session, password_hash, verify

FEED = "SKU;stock\n" + "".join(f"A{n:03};{n % 7}\n" for n in range(200))


def rows_of(raw):
    return [line.split(";") for line in raw.decode().strip().split("\n")[1:]]


def test_variant_permutes_positive_quantities_and_keeps_zeros():
    varied = proveedor.variar(FEED.encode(), random.Random(3))
    before, after = rows_of(FEED.encode()), rows_of(varied)
    assert varied.startswith(b"SKU;stock\n")
    assert [sku for sku, _ in before] == [sku for sku, _ in after]
    assert Counter(q for _, q in before) == Counter(q for _, q in after)
    assert all(a == b for (_, b), (_, a) in zip(before, after, strict=True) if b == "0")
    changed = sum(b != a for (_, b), (_, a) in zip(before, after, strict=True))
    assert 0 < changed <= round(200 * 0.4)
    assert proveedor.variar(FEED.encode(), random.Random(3)) == varied


def test_provider_service_serves_variants_and_archived_bytes(tmp_path, monkeypatch):
    (tmp_path / "celesa.csv").write_text(FEED, encoding="utf-8")
    monkeypatch.setenv("FEEDS_DIR", str(tmp_path))
    client = TestClient(proveedor.app)
    assert client.get("/celesa.csv?no-changes=true").content == FEED.encode()
    assert len(rows_of(client.get("/celesa.csv").content)) == 200
    assert client.get("/otro.csv").status_code == 404
    assert client.get("/..%2F.env").status_code == 404
    assert (tmp_path / "celesa.csv").read_text(encoding="utf-8") == FEED


def test_store_sample_is_half_of_distinct_skus_with_zero_stock(tmp_path):
    feed = tmp_path / "feed.csv"
    feed.write_text(FEED + "A000;9\n", encoding="utf-8")
    items = cli.sample_catalog("T1", feed, 0.5)
    assert len(items) == 100
    assert [i["id"] for i in items[:2]] == ["ITEM000001", "ITEM000002"]
    assert {i["available_quantity"] for i in items} == {0}
    assert len({i["sku"] for i in items}) == 100
    assert items == cli.sample_catalog("T1", feed, 0.5)
    with pytest.raises(ValueError):
        cli.sample_catalog("T1", tmp_path / "falta.csv", 0.5)


def demo_env():
    return {"DEMO_USERNAME": "Admin", "DEMO_PASSWORD_HASH": password_hash("Admin", "00" * 16)}


def test_demo_login_checks_user_and_password_hash():
    env = demo_env()
    assert verify("Admin", "Admin", env)
    assert not verify("Admin", "admin", env)
    assert not verify("admin", "Admin", env)
    assert not verify("Admin", "Admin", {})


def test_user_session_requires_login_and_hides_backend_commands(monkeypatch):
    for key, value in demo_env().items():
        monkeypatch.setenv(key, value)
    answers = iter(["Admin"])
    session = Session(ask=lambda _: next(answers), ask_secret=lambda _: "Admin")
    assert session.handle("status stores") == {"error": "Iniciar sesión con login"}
    assert session.handle("login") == {"status": "authenticated", "demo_login": True}
    assert "desconocido" in session.handle("fault T1 503")["error"]
    assert "desconocido" in session.handle("schedule-now 1")["error"]
    assert session.handle("approve 1") == {"error": "Argumentos inválidos; ver help"}
    assert session.handle("exit") is None
