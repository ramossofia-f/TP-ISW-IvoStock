import pytest
from fastapi.testclient import TestClient

from ivostock.ml import api
from tests.ml.test_normalidad import metrics, observations


@pytest.fixture
def client(monkeypatch):
    from ivostock.ml.config import TrainingConfig
    from ivostock.ml.normalidad import NormalityModel
    from ivostock.ml.training import fit

    monkeypatch.setenv("ML_TOKEN", "service-token")
    model = NormalityModel(fit(observations(), TrainingConfig()))
    monkeypatch.setattr(api, "load_model", lambda: model)
    return TestClient(api.app, headers={"Authorization": "Bearer service-token"})


def test_private_inference_returns_only_decision_score_and_version(client):
    result = client.post("/classify", json={"provider_id": 1, "metrics": metrics()})
    assert result.status_code == 200 and result.json()["accepted"]
    assert set(result.json()) == {"accepted", "score", "version"}


def test_service_authentication_is_required(client):
    client.headers.clear()
    assert client.post("/classify", json={}).status_code == 401
    client.headers["Authorization"] = "Bearer wrong"
    assert client.post("/classify", json={}).status_code == 401


def test_unknown_provider_requests_bootstrap_fallback(client):
    result = client.post("/classify", json={"provider_id": 2, "metrics": metrics()})
    assert result.status_code == 503 and result.json() == {"detail": "insufficient_history"}


@pytest.mark.parametrize("payload", [
    {"provider_id": 0, "metrics": metrics()},
    {"provider_id": 1, "metrics": metrics(rows=-1)},
    {"provider_id": 1, "metrics": metrics(rows=True)},
    {"provider_id": 1, "metrics": {"rows": 1}},
    {"provider_id": 1, "metrics": metrics(), "url": "private-token"},
])
def test_invalid_inputs_are_not_reflected(client, payload):
    result = client.post("/classify", json=payload)
    assert result.status_code == 422 and result.json() == {"detail": "Solicitud ML inválida"}


def test_service_does_not_expose_docs_or_schema(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
