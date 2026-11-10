"""Cuentas de operador, sesiones y protección de la API (RF-01, RNF-11)."""

import importlib.util
import logging
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from ivostock import auth
from ivostock.db import execute, rows

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = {"/health", "/auth/login", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def load_configurar():
    spec = importlib.util.spec_from_file_location("configurar", ROOT / "scripts/configurar.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Sin base de datos -------------------------------------------------------------------


def test_password_hash_verifies_only_the_right_password():
    stored = auth.password_hash("clave-larga", "00" * 16)
    assert stored.startswith("pbkdf2_sha256:200000:") and "$" not in stored
    assert auth.verify_password("clave-larga", stored)
    assert not auth.verify_password("Clave-larga", stored)
    assert not auth.verify_password("", stored)
    assert auth.password_hash("clave-larga") != auth.password_hash("clave-larga")


@pytest.mark.parametrize("stored", ["", "x", "a:b:c:d", "pbkdf2_sha256:1:zz:00", "md5:1:00:00"])
def test_malformed_hash_never_authenticates(stored):
    assert not auth.verify_password("cualquiera", stored)


def test_overlong_password_is_rejected_without_hashing():
    stored = auth.password_hash("a" * 300, "00" * 16)
    assert not auth.verify_password("a" * 300, stored)


def test_parse_operators_validates_every_entry():
    h = auth.password_hash("x", "00" * 16)
    assert auth.parse_operators(f"ana={h}, beto={h}") == [("ana", h), ("beto", h)]
    assert auth.parse_operators("") == []
    for bad in ("ana", f"Ana={h}", f"=x{h}", "ana=sin-formato", f"ana b={h}"):
        with pytest.raises(ValueError):
            auth.parse_operators(bad)


def test_configurar_hashes_match_the_auth_module():
    configurar = load_configurar()
    accounts, passwords = configurar.new_operators()
    parsed = dict(auth.parse_operators(accounts))
    assert list(parsed) == [f"operador{n}" for n in range(1, 6)]
    assert "$" not in accounts
    for name, password in passwords.items():
        assert auth.verify_password(password, parsed[name])
        assert not auth.verify_password(password + "x", parsed[name])
    assert len(set(passwords.values())) == 5


def test_configurar_is_idempotent_and_keeps_passwords_out_of_env(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    configurar = load_configurar()
    configurar.main()
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    passwords = tmp_path / "data/operadores.txt"
    secrets_text = passwords.read_text(encoding="utf-8")
    assert stat.S_IMODE(passwords.stat().st_mode) == 0o600
    assert "OPERATOR_ACCOUNTS=" in env and "DEMO_" not in env
    for line in secrets_text.splitlines():
        assert line.split(": ", 1)[1] not in env
    capsys.readouterr()
    configurar.main()
    assert (tmp_path / ".env").read_text(encoding="utf-8") == env
    assert passwords.read_text(encoding="utf-8") == secrets_text
    assert "Operadores creados" not in capsys.readouterr().out


# --- Con PostgreSQL ----------------------------------------------------------------------


@pytest.fixture
def client(engine, operators):
    from ivostock.main import app

    return TestClient(app)


def login(client, username="ana", password="clave-ana"):
    return client.post("/auth/login", json={"username": username, "password": password})


def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_sync_operators_is_idempotent_and_rotates_hashes(engine, operators, client):
    assert auth.sync_operators(engine, operators) == {"created": 0, "updated": 0, "unchanged": 2}
    token = login(client).json()["token"]
    rotated = operators + ",carla=" + auth.password_hash("c", "22" * 16)
    other = auth.password_hash("nueva", "33" * 16)
    rotated = rotated.replace(operators.split(",")[0], f"ana={other}")
    assert auth.sync_operators(engine, rotated) == {"created": 1, "updated": 1, "unchanged": 1}
    assert client.get("/auth/me", headers=headers(token)).status_code == 401
    assert login(client, "ana", "nueva").status_code == 200
    assert login(client, "ana", "clave-ana").status_code == 401


@pytest.mark.integration
def test_usernames_are_unique_and_validated_by_the_schema(engine, operators):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        execute(conn, "INSERT INTO users(username,password_hash) VALUES ('ana','x')")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        execute(conn, "INSERT INTO users(username,password_hash) VALUES ('Ana','x')")


@pytest.mark.integration
def test_login_returns_a_working_token_and_records_last_login(engine, client):
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "ana" and body["token_type"] == "bearer" and body["expires_at"]
    me = client.get("/auth/me", headers=headers(body["token"]))
    assert me.status_code == 200 and me.json()["username"] == "ana"
    with engine.begin() as conn:
        last = rows(conn, "SELECT last_login_at FROM users WHERE username='ana'")[0]
        assert last["last_login_at"] is not None
        assert (
            rows(conn, "SELECT last_login_at FROM users WHERE username='beto'")[0]["last_login_at"]
            is None
        )


@pytest.mark.integration
def test_username_is_case_insensitive_but_password_is_not(client):
    assert login(client, "  ANA ", "clave-ana").status_code == 200
    assert login(client, "ana", "CLAVE-ANA").status_code == 401


@pytest.mark.integration
def test_wrong_password_unknown_and_inactive_users_look_the_same(engine, client):
    with engine.begin() as conn:
        execute(conn, "UPDATE users SET active=FALSE WHERE username='beto'")
    answers = [
        login(client, "ana", "mal"),
        login(client, "nadie", "clave-ana"),
        login(client, "beto", "clave-beto"),
    ]
    assert {r.status_code for r in answers} == {401}
    assert len({r.text for r in answers}) == 1
    assert "token" not in answers[0].text


@pytest.mark.integration
def test_login_rejects_malformed_bodies(client):
    assert client.post("/auth/login", json={"username": "ana"}).status_code == 422
    assert (
        client.post("/auth/login", json={"username": "a", "password": "x" * 1000}).status_code
        == 422
    )
    assert client.post("/auth/login", content=b"no-json").status_code == 422


@pytest.mark.integration
def test_missing_invalid_and_foreign_tokens_get_401(client):
    for path, method in (("/auth/me", "get"), ("/auth/logout", "post")):
        call = getattr(client, method)
        assert call(path).status_code == 401
        assert call(path, headers=headers("inventado")).status_code == 401
        assert call(path, headers={"Authorization": "Basic YW5hOmNsYXZl"}).status_code == 401
        assert call(path).headers["www-authenticate"] == "Bearer"
    assert client.get("/auth/me").json() == client.get("/auth/me", headers=headers("x")).json()


@pytest.mark.integration
def test_expired_token_is_rejected_and_cleaned_on_next_login(engine, client):
    token = login(client).json()["token"]
    with engine.begin() as conn:
        execute(conn, "UPDATE sessions SET expires_at=now()-interval '1 second'")
    assert client.get("/auth/me", headers=headers(token)).status_code == 401
    login(client, "beto", "clave-beto")
    with engine.begin() as conn:
        assert rows(conn, "SELECT count(*) AS n FROM sessions")[0]["n"] == 1


@pytest.mark.integration
def test_session_ttl_comes_from_the_environment(engine, client, monkeypatch):
    monkeypatch.setenv("SESSION_TTL_MINUTES", "5")
    login(client)
    with engine.begin() as conn:
        minutes = rows(conn, "SELECT extract(epoch FROM expires_at-now())/60 AS m FROM sessions")[
            0
        ]["m"]
    assert 4 < float(minutes) <= 5


@pytest.mark.integration
def test_logout_revokes_only_that_session(client):
    first = login(client).json()["token"]
    second = login(client).json()["token"]
    assert client.post("/auth/logout", headers=headers(first)).json() == {"status": "logged_out"}
    assert client.get("/auth/me", headers=headers(first)).status_code == 401
    assert client.get("/auth/me", headers=headers(second)).status_code == 200


@pytest.mark.integration
def test_deactivating_a_user_closes_their_open_sessions(engine, client):
    token = login(client).json()["token"]
    with engine.begin() as conn:
        execute(conn, "UPDATE users SET active=FALSE WHERE username='ana'")
    assert client.get("/auth/me", headers=headers(token)).status_code == 401


@pytest.mark.integration
def test_database_never_stores_passwords_or_tokens_in_clear(engine, client):
    token = login(client).json()["token"]
    with engine.begin() as conn:
        dump = str(rows(conn, "SELECT * FROM users")) + str(rows(conn, "SELECT * FROM sessions"))
    assert token not in dump and "clave-ana" not in dump and "clave-beto" not in dump
    assert auth.token_hash(token) in dump


@pytest.mark.integration
def test_health_is_public_and_exposes_no_operational_data(client):
    response = client.get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


@pytest.mark.integration
def test_every_route_but_the_public_ones_requires_a_session(client):
    """Recorre el esquema OpenAPI: un endpoint nuevo sin `require_operator` falla aquí."""
    from ivostock.main import app

    protected = 0
    for path, methods in app.openapi()["paths"].items():
        if path in PUBLIC:
            continue
        for method in methods:
            url = path.format_map(Default())
            assert client.request(method, url, json={}).status_code == 401, (method, path)
            protected += 1
    assert protected >= 2


class Default(dict):
    def __missing__(self, key):
        return "1"


@pytest.mark.integration
def test_logs_do_not_contain_passwords_or_tokens(client, caplog):
    with caplog.at_level(logging.INFO, logger="ivostock"):
        login(client, "ana", "intento-fallido-secreto")
        token = login(client).json()["token"]
        client.get("/auth/me", headers=headers(token))
        client.post("/auth/logout", headers=headers(token))
    text = caplog.text + "".join(str(vars(r)) for r in caplog.records)
    assert "intento-fallido-secreto" not in text and "clave-ana" not in text and token not in text
    assert any(
        r.__dict__.get("status") == "ok" and r.__dict__.get("user") == "ana" for r in caplog.records
    )
    rejected = [r for r in caplog.records if r.__dict__.get("status") == "rejected"]
    assert rejected and all("user" not in r.__dict__ for r in rejected)


@pytest.mark.integration
def test_user_session_uses_the_same_accounts_as_the_api(engine, operators):
    from ivostock.usuario import Session

    answers = iter(["beto", "ana"])
    passwords = iter(["clave-ana", "clave-ana"])
    session = Session(
        ask=lambda _: next(answers), ask_secret=lambda _: next(passwords), engine=engine
    )
    assert session.handle("login")["status"] == "rejected"
    assert session.handle("login") == {"status": "authenticated", "user": "ana"}
    assert session.handle("status providers") == []
