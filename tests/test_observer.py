"""El observador sólo hace GET, delega la sesión y no persiste muestras."""

import httpx
import pytest
from fastapi.testclient import TestClient

from ivostock import observer


def test_missing_authentication_performs_no_observation(monkeypatch):
    monkeypatch.setattr(observer.httpx, "get", lambda *a, **kw: pytest.fail("Sin sesión"))
    client = TestClient(observer.app)
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 401
    assert client.get("/openapi.json").status_code == 401


@pytest.mark.parametrize(
    "ml_url,components",
    [
        ("", {"api", "simulator", "provider"}),
        ("http://ml:8002", {"api", "simulator", "provider", "ml", "ml_ready"}),
    ],
)
def test_observation_reads_state_and_pings_components_without_writes(
    monkeypatch, ml_url, components
):
    calls = []
    monkeypatch.setenv("ML_URL", ml_url)

    def get(url, **kwargs):
        calls.append((url, kwargs))
        body = {"status": "ok"} if "/health" in url else {"samples": 7}
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(observer.httpx, "get", get)
    client = TestClient(observer.app)
    result = client.get("/metrics", headers={"Authorization": "Bearer test-only"})
    assert result.status_code == 200
    assert result.json()["summary"] == {"samples": 7}
    assert set(result.json()["http_components"]) == components
    assert len(calls) == 2 + len(components)
    assert not any("/classify" in url for url, _ in calls)
    assert all("test-only" not in url for url, _ in calls)


@pytest.mark.parametrize("status,expected", [(401, 401), (403, 401), (422, 422), (500, 503)])
def test_source_failures_do_not_become_healthy_samples(monkeypatch, status, expected):
    def get(url, **kwargs):
        return httpx.Response(
            status, json={"detail": "secret upstream text"}, request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(observer.httpx, "get", get)
    response = TestClient(observer.app).get(
        "/metrics", headers={"Authorization": "Bearer test-only"}
    )
    assert response.status_code == expected
    assert "secret upstream text" not in response.text
