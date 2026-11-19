import json

import pytest

from ivostock import cli
from ivostock.usuario import Session


@pytest.mark.parametrize("category", ["runs", "quarantines"])
def test_operator_cli_hides_the_same_ml_fields_as_the_http_interface(monkeypatch, category):
    row = {"id": 1, "provider_id": 1, "status": "quarantined", "replay_of": None,
           "started_at": "2026-11-17T00:00:00Z", "finished_at": None, "error": None,
           "snapshot_key": "private-snapshot", "metrics": {"p": 0,
           "ml": {"score": -0.8, "version": "private-model-version", "source": "ml"}}}
    monkeypatch.setattr(cli, "execute", lambda args: (True, [row]))
    session = Session(engine=object())
    session.user = "operador"
    result = session.handle("status " + category)
    assert result[0]["status"] == "quarantined" and result[0]["metrics"]["p"] == 0
    text = json.dumps(result)
    assert "private-model-version" not in text and "private-snapshot" not in text
    assert '"ml"' not in text and '"score"' not in text


def test_operator_cli_does_not_expose_backend_learning_commands():
    session = Session(engine=object())
    session.user = "operador"
    assert "desconocido" in session.handle("ml-report")["error"]
    assert "desconocido" in session.handle("ml-reproduce version")["error"]
