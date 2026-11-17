import asyncio
import time

import httpx
import pytest

from ivostock.ml import client

METRICS = {"rows": 50, "sku": 50, "discarded": [], "parse_error_rate": 0,
           "D": 0, "Z": 0, "p": 0}


@pytest.fixture
def configure(monkeypatch):
    monkeypatch.setenv("ML_URL", "http://ml-private")
    monkeypatch.setenv("ML_TOKEN", "secret-for-tests")
    original = httpx.AsyncClient

    def use(handler):
        transport = httpx.MockTransport(handler)
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
            transport=transport, **kwargs))
    return use


def test_only_current_statistics_and_provider_are_sent(configure):
    def handler(request):
        import json
        assert request.url.path == "/classify"
        assert request.headers["Authorization"] == "Bearer secret-for-tests"
        payload = json.loads(request.content)
        assert payload == {"provider_id": 17, "metrics": {**METRICS, "discarded": 0}}
        return httpx.Response(200, json={"accepted": True, "score": 0, "version": "a" * 64})
    configure(handler)
    decision = client.evaluate(17, {**METRICS, "snapshot_key": "private", "sha256": "private"})
    assert decision["source"] == "ml" and decision["accepted"]


@pytest.mark.parametrize("ml_accepts", [True, False])
@pytest.mark.parametrize("p", [0, 0.5, 0.50001, 0.9, 1])
def test_quarantine_is_guard_or_ml(configure, ml_accepts, p):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={
            "accepted": ml_accepts, "score": 0.2 if ml_accepts else -0.2, "version": "a" * 64})

    configure(handler)
    result = client.evaluate(1, {**METRICS, "p": p})
    assert result["accepted"] is (p <= 0.5 and ml_accepts)
    assert result["guard_accepted"] is (p <= 0.5)
    assert result["fallback_reason"] is None
    assert len(calls) == (1 if p <= 0.5 else 0)
    assert result["source"] == ("ml" if p <= 0.5 else "rules")
    assert result["version"] == ("a" * 64 if p <= 0.5 else None)


@pytest.mark.parametrize("p,expected", [(0, True), (0.5, True), (0.51, False)])
def test_outage_uses_rules_without_changing_their_threshold(configure, p, expected):
    def down(request):
        raise httpx.ConnectError("http://private-with-secret", request=request)
    configure(down)
    result = client.evaluate(1, {**METRICS, "p": p})
    assert result["source"] == "rules" and result["accepted"] is expected
    assert result["fallback_reason"] == ("unavailable" if expected else None)


def test_missing_configuration_is_explicit(monkeypatch):
    monkeypatch.delenv("ML_TOKEN", raising=False)
    assert client.evaluate(1, METRICS)["fallback_reason"] == "unconfigured"


def test_bootstrap_is_distinguished_from_an_outage(configure):
    configure(lambda request: httpx.Response(503, json={"detail": "insufficient_history"}))
    assert client.evaluate(1, METRICS)["fallback_reason"] == "insufficient_history"


def test_whole_request_has_one_second_deadline_and_no_retry(configure):
    calls = []

    async def slow(request):
        calls.append(request)
        await asyncio.sleep(5)
        return httpx.Response(200)

    configure(slow)
    started = time.monotonic()
    assert client.evaluate(1, METRICS)["fallback_reason"] == "timeout"
    assert time.monotonic() - started < 1.5 and len(calls) == 1


@pytest.mark.parametrize("reply", [
    {"accepted": True, "score": -0.8, "version": "a" * 64},
    {"accepted": "true", "score": 0, "version": "a" * 64},
    {"accepted": True, "score": "NaN", "version": "a" * 64},
    {"accepted": True, "score": 0, "version": "bad"},
])
def test_invalid_service_result_falls_back(configure, reply):
    configure(lambda request: httpx.Response(200, json=reply))
    assert client.evaluate(1, METRICS)["fallback_reason"] == "invalid_response"


def test_outage_logs_do_not_disclose_private_url_or_token(configure, caplog):
    def down(request):
        raise httpx.ConnectError("http://private-with-secret", request=request)
    configure(down)
    client.evaluate(1, METRICS)
    assert "private-with-secret" not in caplog.text and "secret-for-tests" not in caplog.text
