"""Interfaz estática de configuración (RF-25, ADR-0013).

No requieren PostgreSQL: la interfaz se sirve sin sesión y los endpoints que usa se comparan con
el esquema OpenAPI, que se genera sin tocar la base.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
CALL = re.compile(r"""\bapi\(\s*'([A-Z]+)'\s*,\s*(['"`])(.*?)\2""")

# Lo que la interfaz necesita de la API: si se rompe una llamada, esta lista lo delata.
REQUIRED = {
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
    ("GET", "/auth/me"),
    ("GET", "/providers"),
    ("POST", "/providers"),
    ("POST", "/providers/{}/disable"),
    ("GET", "/providers/{}/suggestions"),
    ("POST", "/providers/{}/approve"),
    ("GET", "/stores"),
    ("GET", "/stores/available"),
    ("POST", "/stores"),
    ("GET", "/links"),
    ("GET", "/links/summary"),
    ("POST", "/links/{}/off"),
    ("POST", "/links/{}/resume"),
    ("GET", "/runs"),
    ("GET", "/runs/summary"),
}


@pytest.fixture(scope="module")
def app():
    from ivostock.main import app

    return app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def static_dir():
    from ivostock.main import STATIC_DIR

    return STATIC_DIR


def normalise(path):
    """`/links/{link_id}/off` y `/links/${Number(id)}/off` pasan a `/links/{}/off`."""
    return re.sub(r"\$?\{[^}]*\}", "{}", path)


def test_root_serves_the_interface_without_a_session(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="form-login"' in response.text
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy and "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy and "unsafe-eval" not in policy
    assert response.headers["x-content-type-options"] == "nosniff"


def test_static_assets_are_served(client):
    script = client.get("/static/app.js")
    assert script.status_code == 200 and "javascript" in script.headers["content-type"]
    style = client.get("/static/styles.css")
    assert style.status_code == 200 and style.headers["content-type"].startswith("text/css")
    assert client.get("/static/no-existe.js").status_code == 404


def test_interface_is_not_part_of_the_api_schema(app):
    for path in app.openapi()["paths"]:
        assert path != "/" and not path.startswith("/static"), path


def test_there_is_a_single_route_and_a_single_app(client):
    assert client.get("/configuracion").status_code == 404
    assert not (ROOT / "main.py").exists(), "main.py de la raíz duplica a src/ivostock/main.py"
    assert not (ROOT / "ADR-0010.md").exists()


def test_static_files_live_inside_the_package(static_dir):
    # Dentro del paquete instalado (en la imagen, `--no-editable`), no relativo al directorio actual.
    import ivostock

    assert static_dir.is_absolute()
    assert static_dir == Path(ivostock.__file__).resolve().parent / "static"
    assert {p.name for p in static_dir.iterdir()} >= {"index.html", "app.js", "styles.css"}


def test_data_is_never_rendered_as_html(static_dir):
    script = (static_dir / "app.js").read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert forbidden not in script, forbidden
    page = (static_dir / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"\son[a-z]+\s*=", page), "manejador de eventos en línea"
    assert not re.search(r"\sstyle\s*=", page), "estilo en línea"
    assert not re.findall(r"<script(?![^>]*\bsrc=)", page), "script en línea"
    assert not re.search(r"<style", page), "hoja de estilo en línea"


def test_session_is_real_and_kept_in_session_storage(static_dir):
    script = (static_dir / "app.js").read_text(encoding="utf-8")
    assert "const API_BASE = '';" in script
    assert "mock" not in script.lower() and "'/api'" not in script
    assert "sessionStorage" in script and "localStorage" not in script


def test_interface_only_calls_documented_endpoints(app, static_dir):
    script = (static_dir / "app.js").read_text(encoding="utf-8")
    documented = {
        (method.upper(), normalise(path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    used = {(method, normalise(path)) for method, _, path in CALL.findall(script)}
    assert used - documented == set()
    assert REQUIRED - used == set()
