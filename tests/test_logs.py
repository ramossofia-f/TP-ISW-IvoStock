import json
import logging

from ivostock.logs import FormatoJson


def test_registro_json_conserva_contexto_operativo():
    registro = logging.makeLogRecord(
        {
            "name": "ivostock.ingesta",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Corrida aceptada",
            "run": 7,
            "provider": 2,
        }
    )
    datos = json.loads(FormatoJson().format(registro))
    assert datos["run"] == 7 and datos["provider"] == 2
    assert datos["mensaje"] == "Corrida aceptada"


def test_excepcion_no_filtra_url_ni_credenciales():
    error = ConnectionError("https://example.invalid/?token=NO-PUBLICAR")
    registro = logging.makeLogRecord(
        {
            "name": "ivostock.ingesta",
            "levelno": logging.ERROR,
            "levelname": "ERROR",
            "msg": "Descarga fallida",
            "exc_info": (type(error), error, None),
        }
    )
    text = FormatoJson().format(registro)
    assert json.loads(text)["error"] == "ConnectionError"
    assert "NO-PUBLICAR" not in text and "example.invalid" not in text
