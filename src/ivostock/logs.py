"""Logging JSON con contexto explícito y excepciones sin contenido sensible."""

import json
import logging
import sys

CAMPOS_TRAZA = (
    "component",
    "run",
    "provider",
    "store",
    "link",
    "revision",
    "attempt",
    "status",
    "http_status",
    "error",
)


class FormatoJson(logging.Formatter):
    def format(self, registro):
        datos = {
            "nivel": registro.levelname,
            "logger": registro.name,
            "mensaje": registro.getMessage(),
        }
        for campo in CAMPOS_TRAZA:
            if hasattr(registro, campo):
                datos[campo] = getattr(registro, campo)
        if registro.exc_info:
            datos["error"] = registro.exc_info[0].__name__
        return json.dumps(datos, ensure_ascii=False)


def configurar(stream=None):
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(FormatoJson())
    logger = logging.getLogger("ivostock")
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]
    logger.propagate = False
