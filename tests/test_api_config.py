"""API de configuración (RF-02..RF-09, RF-25, RNF-11, RNF-16): cada endpoint por HTTP real."""

import logging
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from ivostock import cli, marketplace, services
from ivostock.api_models import LinkOut, ProviderOut
from ivostock.db import execute, rows
from ivostock.errors import Conflict, NotFound, ServiceError, UpstreamError
from ivostock.publisher import publish_once
from tests.helpers import admin, drain, import_catalogs, seed

pytestmark = pytest.mark.integration


@pytest.fixture
def api(engine, operators):
    from ivostock.main import app

    client = TestClient(app)
    login = client.post("/auth/login", json={"username": "ana", "password": "clave-ana"})
    client.headers["Authorization"] = "Bearer " + login.json()["token"]
    return client


def create_provider(api, feed_server, name="Proveedor"):
    response = api.post("/providers", json={"name": name, "url": feed_server["url"]})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_store(api, engine, store="T1", items=3):
    seed(store, items)
    assert api.post("/stores", json={"store": store}).status_code == 201
    import_catalogs(engine)


def world(api, engine, feed_server, items=3, ingest=True):
    """Tienda T1 importada y un proveedor; con `ingest`, ya con su primera corrida aceptada."""
    add_store(api, engine, "T1", items)
    provider = create_provider(api, feed_server)
    if ingest:
        assert services.ingest(engine, provider)["status"] == "accepted"
    return provider


def linked(api, engine, feed_server, items=3, publish=True):
    provider = world(api, engine, feed_server, items)
    approved = api.post(f"/providers/{provider}/approve", json={"store": "T1", "all": True})
    assert approved.json() == {"approved": items, "awaiting_ingest": False}
    services.compare_once(engine)
    if publish:
        drain(engine)
    return provider


def links(engine):
    with engine.begin() as conn:
        return rows(conn, "SELECT * FROM links ORDER BY id")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# --- Proveedores (B2) ----------------------------------------------------------------------


def test_create_provider_validates_the_source_and_reports_the_preview(api, feed_server):
    response = api.post("/providers", json={"name": "  Celesa  ", "url": feed_server["url"]})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "validated" and body["sku"] == 50
    assert body["parse_error_rate"] == 0 and body["parse_alert"] is False
    assert body["awaiting_first_ingest"] is True and body["next_run_at"]
    assert len(body["preview"]) == 5 and set(body["preview"][0]) == {"sku", "stock"}
    assert body["suggestions"] == []
    assert api.get("/providers").json()[0]["name"] == "Celesa"


def test_parse_error_rate_above_ten_percent_raises_the_alert(api, feed_server):
    good = "".join(f"A{n:03};5\n" for n in range(10))
    bad = "".join(f"B{n};abc\n" for n in range(5))
    feed_server["path"].write_text("SKU;stock\n" + good + bad, encoding="utf-8")
    body = api.post("/providers", json={"name": "Ruidoso", "url": feed_server["url"]}).json()
    assert body["sku"] == 10 and body["parse_error_rate"] > 0.10 and body["parse_alert"] is True


def test_create_provider_reports_matching_suggestions_for_imported_stores(api, engine, feed_server):
    add_store(api, engine, "T1", items=4)
    body = api.post("/providers", json={"name": "P", "url": feed_server["url"]}).json()
    (suggestion,) = body["suggestions"]
    assert suggestion["store"] == "T1" and suggestion["total"] == 4
    assert set(suggestion["examples"][0]) == {"item_id", "sku", "desired", "confirmed"}


def test_duplicate_provider_name_is_a_conflict_and_keeps_the_original(api, feed_server):
    create_provider(api, feed_server, "Celesa")
    response = api.post("/providers", json={"name": "Celesa", "url": feed_server["url"]})
    assert response.status_code == 409
    assert response.json() == {"detail": "Ya existe un proveedor con ese nombre"}
    assert [p["name"] for p in api.get("/providers").json()] == ["Celesa"]


def test_source_failures_are_explained_without_leaking_the_url(api, engine, feed_server):
    missing = api.post(
        "/providers", json={"name": "A", "url": feed_server["url"].replace("feed", "otro")}
    )
    assert missing.status_code == 502
    assert missing.json() == {"detail": "La fuente respondió HTTP 404"}
    down = api.post("/providers", json={"name": "B", "url": f"http://127.0.0.1:{free_port()}/x"})
    assert down.status_code == 502
    assert down.json()["detail"].startswith("No se pudo descargar la fuente")
    assert "127.0.0.1" not in down.text
    feed_server["path"].write_text("A;1\n", encoding="utf-8")
    assert api.post("/providers", json={"name": "C", "url": feed_server["url"]}).status_code == 422
    feed_server["path"].write_bytes(b"SKU;stock\n\xff\xfe;1\n")
    binary = api.post("/providers", json={"name": "D", "url": feed_server["url"]})
    assert binary.status_code == 422 and "UTF-8" in binary.json()["detail"]
    assert api.get("/providers").json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"url": "http://x/f.csv"},
        {"name": "", "url": "http://x/f.csv"},
        {"name": "x" * 101, "url": "http://x/f.csv"},
        {"name": "P", "url": "ftp://x/f.csv"},
        {"name": "P", "url": "file:///etc/passwd"},
        {"name": "P", "url": "http://"},
        {"name": "P", "url": "http://usuario:clave-secreta@x/f.csv"},
        {"name": "P", "url": "http://x/f.csv", "extra": 1},
        {"name": "P", "url": 5},
    ],
)
def test_provider_input_is_validated_and_never_echoed(api, body):
    response = api.post("/providers", json=body)
    assert response.status_code == 422
    assert "clave-secreta" not in response.text
    assert all(set(e) == {"type", "loc", "msg"} for e in response.json()["detail"])


def test_provider_listing_omits_the_url(api, feed_server):
    provider = create_provider(api, feed_server)
    (item,) = api.get("/providers").json()
    assert set(item) == set(ProviderOut.model_fields) and "url" not in item
    assert item["id"] == provider and item["active"] is True and item["status"] == "validated"
    assert feed_server["url"] not in api.get("/providers").text


def test_disable_provider_zeroes_its_links_before_deactivating(api, engine, feed_server):
    provider = linked(api, engine, feed_server, items=3)
    response = api.post(f"/providers/{provider}/disable")
    assert response.status_code == 202
    assert response.json() == {"provider": provider, "cuts": 3}
    assert all(link["cut_requested"] and link["state"] == "active" for link in links(engine))
    assert api.get("/providers").json()[0]["active"] is False
    drain(engine)
    assert {(link["state"], link["confirmed"]) for link in links(engine)} == {("inactive", 0)}
    assert api.post(f"/providers/{provider}/disable").status_code == 409


def test_disable_unknown_provider_and_bad_ids(api):
    assert api.post("/providers/999/disable").status_code == 404
    assert api.post("/providers/999/disable").json() == {"detail": "Proveedor inexistente"}
    for bad in ("0", "-1", "abc", str(2**63)):
        assert api.post(f"/providers/{bad}/disable").status_code == 422


# --- Tiendas (B3) --------------------------------------------------------------------------


def test_unknown_marketplace_store_is_rejected_and_not_registered(api, engine):
    response = api.post("/stores", json={"store": "T9"})
    assert response.status_code == 404
    assert response.json() == {"detail": "La tienda no existe en el marketplace"}
    assert api.get("/stores").json() == []


def test_add_store_reports_import_progress_until_complete(api, engine):
    seed("T1", 250)
    created = api.post("/stores", json={"store": "T1"})
    assert created.status_code == 201
    assert created.json() == {
        "id": "T1",
        "status": "importing",
        "catalog_imported": False,
        "processed": 0,
        "total": None,
        "progress_percent": 0.0,
        "last_error": None,
    }
    assert services.import_page(engine)
    (half,) = api.get("/stores").json()
    assert (half["processed"], half["total"], half["progress_percent"]) == (100, 250, 40.0)
    assert half["catalog_imported"] is False
    import_catalogs(engine)
    (done,) = api.get("/stores").json()
    assert (done["processed"], done["total"], done["progress_percent"]) == (250, 250, 100.0)
    assert done["catalog_imported"] is True and done["status"] == "healthy"


def test_adding_an_existing_store_is_idempotent(api, engine):
    seed("T1", 3)
    assert api.post("/stores", json={"store": "T1"}).status_code == 201
    import_catalogs(engine)
    again = api.post("/stores", json={"store": "T1"})
    assert again.status_code == 200 and again.json()["catalog_imported"] is True
    assert len(api.get("/stores").json()) == 1
    with engine.begin() as conn:
        assert rows(conn, "SELECT count(*) AS n FROM catalog")[0]["n"] == 3


@pytest.mark.parametrize("store", ["", "a/b", "../x", "T 1", "x" * 33, "T1?x=1"])
def test_store_ids_are_validated(api, store):
    assert api.post("/stores", json={"store": store}).status_code == 422
    assert api.get("/links", params={"store": store}).status_code == 422


def test_marketplace_failures_do_not_register_the_store(api, engine, monkeypatch):
    def refuse(*args, **kwargs):
        raise httpx.ConnectError("no conecta con http://usuario:secreto@mkt")

    monkeypatch.setattr(marketplace, "market_request", refuse)
    down = api.post("/stores", json={"store": "T1"})
    assert down.status_code == 502 and "secreto" not in down.text
    monkeypatch.setattr(marketplace, "market_request", lambda *a, **k: httpx.Response(401))
    assert api.post("/stores", json={"store": "T1"}).json() == {
        "detail": "El marketplace respondió HTTP 401"
    }
    assert api.get("/stores").json() == []


def test_second_store_reuses_the_ingested_inventory(api, engine, feed_server):
    provider = linked(api, engine, feed_server, items=3)
    runs = len(services.status(engine, "runs"))
    add_store(api, engine, "T2", items=3)
    suggestions = api.get(f"/providers/{provider}/suggestions", params={"store": "T2"}).json()
    assert suggestions["total"] == 3
    approved = api.post(f"/providers/{provider}/approve", json={"store": "T2", "all": True})
    assert approved.json() == {"approved": 3, "awaiting_ingest": False}
    services.compare_once(engine)
    drain(engine)
    assert len(services.status(engine, "runs")) == runs
    assert {link["store_id"] for link in links(engine)} == {"T1", "T2"}
    assert {link["state"] for link in links(engine)} == {"active"}
    assert {link["confirmed"] for link in links(engine)} == {10}


# --- Sugerencias y aprobación (B4, RF-07) --------------------------------------------------


def test_suggestions_filter_limit_and_use_the_stored_inventory(api, engine, feed_server):
    stock = dict(feed_server["stock"], A001=0)
    feed_server["write"](stock)
    provider = world(api, engine, feed_server, items=3)
    runs = len(services.status(engine, "runs"))
    url = f"/providers/{provider}/suggestions"
    everything = api.get(url, params={"store": "T1"}).json()
    assert everything["total"] == 3 and len(everything["items"]) == 3
    assert api.get(url, params={"store": "T1", "limit": 2}).json()["total"] == 3
    assert len(api.get(url, params={"store": "T1", "limit": 2}).json()["items"]) == 2
    by_sku = api.get(url, params={"store": "T1", "sku": "A001"}).json()
    assert [i["sku"] for i in by_sku["items"]] == ["A001"] and by_sku["items"][0]["desired"] == 0
    positive = api.get(url, params={"store": "T1", "positive_only": "true"}).json()
    assert sorted(i["sku"] for i in positive["items"]) == ["A000", "A002"]
    assert len(services.status(engine, "runs")) == runs


def test_suggestion_preconditions(api, engine, feed_server):
    provider = world(api, engine, feed_server)
    url = f"/providers/{provider}/suggestions"
    assert api.get("/providers/999/suggestions", params={"store": "T1"}).status_code == 404
    assert api.get(url, params={"store": "T9"}).json() == {"detail": "Tienda inexistente"}
    seed("T2", 3)
    api.post("/stores", json={"store": "T2"})
    importing = api.get(url, params={"store": "T2"})
    assert importing.status_code == 409 and "importando" in importing.json()["detail"]
    assert api.get(url).status_code == 422
    for limit in (0, 201):
        assert api.get(url, params={"store": "T1", "limit": limit}).status_code == 422
    api.post(f"/providers/{provider}/disable")
    assert api.get(url, params={"store": "T1"}).json() == {
        "detail": "El proveedor está dado de baja"
    }


def test_approve_by_count_items_and_all(api, engine, feed_server):
    provider = world(api, engine, feed_server, items=5)
    url = f"/providers/{provider}/approve"
    assert api.post(url, json={"store": "T1", "count": 2}).json() == {
        "approved": 2,
        "awaiting_ingest": False,
    }
    assert [link["item_id"] for link in links(engine)] == ["I0", "I1"]
    assert api.post(url, json={"store": "T1", "items": ["I3"]}).json()["approved"] == 1
    assert api.post(url, json={"store": "T1", "all": True}).json()["approved"] == 2
    assert api.post(url, json={"store": "T1", "all": True}).json()["approved"] == 0
    assert len(links(engine)) == 5


def test_approve_before_the_first_ingest_waits_for_it(api, engine, feed_server):
    provider = world(api, engine, feed_server, items=2, ingest=False)
    response = api.post(f"/providers/{provider}/approve", json={"store": "T1", "all": True})
    assert response.json() == {"approved": 2, "awaiting_ingest": True}
    assert api.get("/links/summary").json()["awaiting_ingest"] == 2


def test_approve_positive_only(api, engine, feed_server):
    feed_server["write"](dict(feed_server["stock"], A001=0))
    provider = world(api, engine, feed_server, items=3)
    response = api.post(
        f"/providers/{provider}/approve", json={"store": "T1", "all": True, "positive_only": True}
    )
    assert response.json()["approved"] == 2
    assert sorted(link["sku"] for link in links(engine)) == ["A000", "A002"]


@pytest.mark.parametrize(
    "body",
    [
        {"store": "T1"},
        {"store": "T1", "all": False},
        {"store": "T1", "all": True, "count": 1},
        {"store": "T1", "items": ["I0"], "count": 1},
        {"store": "T1", "items": []},
        {"store": "T1", "items": ["x" * 65]},
        {"store": "T1", "count": 0},
        {"items": ["I0"]},
    ],
)
def test_approve_requires_exactly_one_valid_selection(api, engine, feed_server, body):
    provider = world(api, engine, feed_server)
    assert api.post(f"/providers/{provider}/approve", json=body).status_code == 422
    assert links(engine) == []


def test_a_second_active_assignment_of_a_listing_is_rejected(api, engine, feed_server):
    first = world(api, engine, feed_server, items=3)
    api.post(f"/providers/{first}/approve", json={"store": "T1", "count": 2})
    second = create_provider(api, feed_server, "Otro")
    assert services.ingest(engine, second)["status"] == "accepted"
    taken = api.post(f"/providers/{second}/approve", json={"store": "T1", "items": ["I0"]})
    assert taken.status_code == 409
    assert taken.json() == {"detail": "Publicación no disponible para vincular"}
    mixed = api.post(f"/providers/{second}/approve", json={"store": "T1", "items": ["I2", "I1"]})
    assert mixed.status_code == 409
    assert [link["item_id"] for link in links(engine)] == ["I0", "I1"]
    only_free = api.get(f"/providers/{second}/suggestions", params={"store": "T1"}).json()
    assert [i["item_id"] for i in only_free["items"]] == ["I2"]
    assert (
        api.post(f"/providers/{second}/approve", json={"store": "T1", "all": True}).json()[
            "approved"
        ]
        == 1
    )
    with engine.begin() as conn:
        dup = rows(
            conn,
            "SELECT count(*) AS n FROM (SELECT store_id,item_id FROM links WHERE state!='inactive' "
            "GROUP BY 1,2 HAVING count(*)>1) d",
        )
    assert dup[0]["n"] == 0


def test_losing_the_race_for_a_listing_is_a_conflict_not_a_500(
    api, engine, feed_server, monkeypatch
):
    first = world(api, engine, feed_server, items=2)
    api.post(f"/providers/{first}/approve", json={"store": "T1", "items": ["I0"]})
    second = create_provider(api, feed_server, "Otro")
    stale = [{"item_id": "I0", "sku": "A000", "desired": 10, "confirmed": 0}]
    monkeypatch.setattr(services, "suggestions", lambda *args, **kwargs: stale)
    response = api.post(f"/providers/{second}/approve", json={"store": "T1", "items": ["I0"]})
    assert response.status_code == 409
    assert response.json() == {"detail": "Alguna publicación ya tiene un vínculo activo"}
    assert len(links(engine)) == 1


def test_approve_preconditions(api, engine, feed_server):
    provider = world(api, engine, feed_server)
    body = {"store": "T1", "all": True}
    assert api.post("/providers/999/approve", json=body).status_code == 404
    assert (
        api.post(f"/providers/{provider}/approve", json={**body, "store": "T9"}).status_code == 404
    )
    seed("T2", 2)
    api.post("/stores", json={"store": "T2"})
    assert (
        api.post(f"/providers/{provider}/approve", json={**body, "store": "T2"}).status_code == 409
    )
    assert links(engine) == []


# --- Vínculos: listado, resumen, apagar y reanudar (B4) ------------------------------------


def test_links_summary_follows_the_link_lifecycle(api, engine, feed_server):
    linked(api, engine, feed_server, items=5, publish=False)
    pending = api.get("/links/summary").json()
    assert (pending["total"], pending["pending"], pending["synchronized"]) == (5, 5, 0)
    drain(engine)
    done = api.get("/links/summary", params={"store": "T1"}).json()
    assert (done["total"], done["synchronized"], done["pending"]) == (5, 5, 0)
    assert (done["changed_from_initial"], done["positive_confirmed"], done["zero_confirmed"]) == (
        5,
        5,
        0,
    )
    assert api.get("/links/summary", params={"store": "T9"}).status_code == 404


def test_links_are_paginated_in_id_order(api, engine, feed_server):
    linked(api, engine, feed_server, items=5)

    def page(**params):
        body = api.get("/links", params=params).json()
        return [item["id"] for item in body["items"]], body["next_offset"]

    assert page(limit=2) == ([1, 2], 2)
    assert page(limit=2, offset=2) == ([3, 4], 4)
    assert page(limit=2, offset=4) == ([5], None)
    assert page(limit=5) == ([1, 2, 3, 4, 5], None)
    assert page(offset=50) == ([], None)
    assert page(store="T1", limit=3) == ([1, 2, 3], 3)
    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}):
        assert api.get("/links", params=bad).status_code == 422
    assert api.get("/links", params={"store": "T9"}).status_code == 404


def test_link_payload_has_a_fixed_shape_and_short_errors(api, engine, feed_server):
    linked(api, engine, feed_server, items=1)
    with engine.begin() as conn:
        execute(conn, "UPDATE links SET last_error=:e", e="x" * 2000)
    (item,) = api.get("/links").json()["items"]
    assert set(item) == set(LinkOut.model_fields)
    assert item["state"] == "active" and item["confirmed"] == 10 and item["pending"] is False
    assert len(item["last_error"]) == 500


def test_turn_off_link_confirms_zero_before_deactivating(api, engine, feed_server):
    linked(api, engine, feed_server, items=2)
    response = api.post("/links/1/off")
    assert response.status_code == 202 and response.json() == {"link": 1, "cuts": 1}
    first = links(engine)[0]
    assert first["state"] == "active" and first["cut_requested"] and first["desired"] == 0
    drain(engine)
    assert [(link["state"], link["confirmed"]) for link in links(engine)] == [
        ("inactive", 0),
        ("active", 10),
    ]
    assert api.post("/links/1/off").status_code == 409
    assert api.post("/links/999/off").json() == {"detail": "Vínculo inexistente"}
    assert api.post("/links/0/off").status_code == 422


def test_resume_requeues_a_failed_link(api, engine, feed_server):
    linked(api, engine, feed_server, items=1, publish=False)
    admin("/admin/fault", {"store": "T1", "status": 404, "remaining": 1})
    assert publish_once(engine)
    (failed,) = api.get("/links").json()["items"]
    assert failed["state"] == "error" and failed["last_error"] and failed["pending"] is False
    assert api.get("/links/summary").json()["failed"] == 1
    response = api.post("/links/1/resume")
    assert response.status_code == 200 and response.json() == {"link": 1, "status": "resumed"}
    (queued,) = api.get("/links").json()["items"]
    assert queued["state"] == "active" and queued["last_error"] is None and queued["pending"]
    drain(engine)
    assert api.get("/links/summary").json()["synchronized"] == 1


def test_resume_rejects_unknown_and_inactive_links(api, engine, feed_server):
    linked(api, engine, feed_server, items=1)
    assert api.post("/links/999/resume").json() == {"detail": "Vínculo inexistente"}
    api.post("/links/1/off")
    drain(engine)
    assert api.post("/links/1/resume").status_code == 409


# --- Autenticación, OpenAPI y errores (B5, B6, RNF-11, RNF-16) ------------------------------

OPERATIONS = {
    ("post", "/auth/login"),
    ("post", "/auth/logout"),
    ("get", "/auth/me"),
    ("get", "/providers"),
    ("post", "/providers"),
    ("post", "/providers/{provider_id}/disable"),
    ("get", "/providers/{provider_id}/suggestions"),
    ("post", "/providers/{provider_id}/approve"),
    ("get", "/stores"),
    ("post", "/stores"),
    ("get", "/links"),
    ("get", "/links/summary"),
    ("post", "/links/{link_id}/off"),
    ("post", "/links/{link_id}/resume"),
    ("get", "/health"),
}


def test_every_endpoint_rejects_missing_or_foreign_tokens(engine, operators):
    from ivostock.main import app

    anonymous = TestClient(app)
    for path, methods in app.openapi()["paths"].items():
        if path in ("/health", "/auth/login"):
            continue
        for method in methods:
            url = path.format(provider_id=1, link_id=1)
            for headers in ({}, {"Authorization": "Bearer inventado"}):
                response = anonymous.request(method, url, json={}, headers=headers)
                assert response.status_code == 401, (method, path)


def test_openapi_documents_exactly_what_is_implemented(engine):
    from ivostock.main import app

    schema = app.openapi()
    documented = {(m, p) for p, ops in schema["paths"].items() for m in ops}
    assert documented == OPERATIONS
    text = " ".join(schema["paths"]).lower()
    for forbidden in ("fault", "schedule", "monitor", "compare", "publish", "admin", "seed"):
        assert forbidden not in text
    public = {("get", "/health"), ("post", "/auth/login")}
    for method, path in OPERATIONS:
        operation = schema["paths"][path][method]
        assert operation.get("summary") and operation.get("tags")
        if (method, path) not in public:
            assert operation.get("security") == [{"HTTPBearer": []}], (method, path)
            assert "401" in operation["responses"] and "500" in operation["responses"]
    assert "url" not in schema["components"]["schemas"]["ProviderOut"]["properties"]


def test_validation_errors_do_not_echo_what_the_client_sent(engine, operators):
    from ivostock.main import app

    response = TestClient(app).post(
        "/auth/login", json={"username": "ana", "password": "intento-secreto" + "x" * 300}
    )
    assert response.status_code == 422 and "intento-secreto" not in response.text


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ServiceError("dato inválido"), 422),
        (NotFound("no existe"), 404),
        (Conflict("choca"), 409),
        (UpstreamError("externo caído"), 502),
        (ValueError("regla de negocio"), 422),
    ],
)
def test_business_errors_map_to_their_http_status(api, monkeypatch, error, code):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(services, "status", fail)
    response = api.get("/providers")
    assert response.status_code == code and response.json() == {"detail": str(error)}


def test_unexpected_errors_are_500_without_detail_or_traceback(api, monkeypatch, caplog):
    def explode(*args, **kwargs):
        raise RuntimeError("postgresql://usuario:clave-db@host/db?token=abc123")

    monkeypatch.setattr(services, "status", explode)
    with caplog.at_level(logging.INFO, logger="ivostock"):
        response = api.get("/providers")
    assert response.status_code == 500 and response.json() == {"detail": "Error interno"}
    dump = caplog.text + "".join(str(vars(r)) for r in caplog.records)
    assert "clave-db" not in dump and "abc123" not in dump
    (record,) = [r for r in caplog.records if r.name == "ivostock.api"]
    assert record.error == "RuntimeError" and record.exc_info is None


def test_database_failures_are_also_500_without_detail(api, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def down(*args, **kwargs):
        raise OperationalError("SELECT 1", {"u": "http://x:y@h"}, Exception("no conecta"))

    monkeypatch.setattr(services, "list_stores", down)
    response = api.get("/stores")
    assert response.status_code == 500 and response.json() == {"detail": "Error interno"}


def test_cli_still_reports_typed_errors_by_message(engine):
    def run(*argv):
        return cli.execute(cli.parser().parse_args(list(argv)))

    assert run("resume", "999") == (False, {"error": "Vínculo inexistente"})
    assert run("off", "999") == (False, {"error": "Vínculo inexistente"})
    assert run("provider-disable", "999") == (False, {"error": "Proveedor inexistente"})
