import logging

import pytest

from ivostock import services
from ivostock.db import execute, rows
from ivostock.generador.feeds import Parametros, generar

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("parameters", [Parametros(truncar=0.3), Parametros(ceros=0.2)])
def test_generador_provoca_cuarentena_sin_tocar_estado(engine, feed_server, parameters):
    provider = services.add_provider(engine, "P2", feed_server["url"])["id"]
    services.ingest(engine, provider)
    feed_server["path"].write_text(generar(parameters, feed_server["stock"]), encoding="utf-8")
    result = services.ingest(engine, provider)
    assert result["status"] == "quarantined"
    with engine.begin() as conn:
        assert {
            row["sku"]: row["quantity"]
            for row in rows(conn, "SELECT sku,quantity FROM stock WHERE provider_id=:p", p=provider)
        } == feed_server["stock"]
        assert (
            rows(
                conn, "SELECT count(*) AS n FROM comparison_events WHERE provider_id=:p", p=provider
            )[0]["n"]
            == 1
        )


def test_repetida_reutiliza_inventario_y_conserva_evento_durable(engine, feed_server):
    provider = services.add_provider(engine, "P2", feed_server["url"])["id"]
    first = services.ingest(engine, provider)
    second = services.ingest(engine, provider, replay_of=first["id"])
    assert second["status"] == "accepted"
    runs = services.status(engine, "runs")
    assert runs[-1]["metrics"]["reused_inventory"] is True
    assert runs[-1]["snapshot_key"] == runs[0]["snapshot_key"]
    with engine.begin() as conn:
        assert (
            rows(
                conn, "SELECT count(*) AS n FROM comparison_events WHERE provider_id=:p", p=provider
            )[0]["n"]
            == 2
        )


def test_falla_no_modifica_estado_ni_loguea_secretos(engine, feed_server, caplog):
    provider = services.add_provider(engine, "P2", feed_server["url"])["id"]
    services.ingest(engine, provider)
    with engine.begin() as conn:
        execute(
            conn,
            "UPDATE providers SET url=:u WHERE id=:p",
            p=provider,
            u=feed_server["url"] + "?token=NO-PUBLICAR",
        )
    feed_server["path"].write_bytes(b"bad header\n")
    with caplog.at_level(logging.WARNING):
        result = services.ingest(engine, provider)
    assert result["status"] == "failed"
    assert "NO-PUBLICAR" not in caplog.text
    assert "NO-PUBLICAR" not in services.status(engine, "runs")[-1]["error"]
    with engine.begin() as conn:
        assert (
            rows(conn, "SELECT count(*) AS n FROM stock WHERE provider_id=:p", p=provider)[0]["n"]
            == 50
        )
