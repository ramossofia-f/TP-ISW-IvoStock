import random
from collections import Counter

from fastapi.testclient import TestClient

from ivostock import auth, proveedor
from ivostock.usuario import Session

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


def test_user_session_requires_login_and_hides_backend_commands(monkeypatch):
    accounts = {("operador1", "clave-correcta")}
    monkeypatch.setattr(
        auth,
        "authenticate",
        lambda engine, user, password: (
            {"id": 1, "username": user} if (user, password) in accounts else None
        ),
    )
    answers = iter(["operador1", "operador1"])
    passwords = iter(["clave-incorrecta", "clave-correcta"])
    session = Session(
        ask=lambda _: next(answers), ask_secret=lambda _: next(passwords), engine=object()
    )
    assert session.handle("status stores") == {"error": "Iniciar sesión con login"}
    assert session.handle("login")["status"] == "rejected"
    assert session.handle("status stores") == {"error": "Iniciar sesión con login"}
    assert session.handle("login") == {"status": "authenticated", "user": "operador1"}
    assert "desconocido" in session.handle("fault T1 503")["error"]
    assert "desconocido" in session.handle("schedule-now 1")["error"]
    assert session.handle("approve 1") == {"error": "Argumentos inválidos; ver help"}
    assert session.handle("logout") == {"status": "logged_out"}
    assert session.handle("status stores") == {"error": "Iniciar sesión con login"}
    assert session.handle("exit") is None
