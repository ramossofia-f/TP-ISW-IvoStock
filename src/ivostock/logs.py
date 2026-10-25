"""Logging estructurado en JSON, con identificador de corrida trazable (RNF-09, ADR-0011)."""

import json
import logging
import sys

CAMPOS_TRAZA = ("corrida_id", "proveedor_id", "estado")


class FormatoJson(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        datos = {
            "nivel": registro.levelname,
            "logger": registro.name,
            "mensaje": registro.getMessage(),
        }
        for campo in CAMPOS_TRAZA:
            if hasattr(registro, campo):
                datos[campo] = getattr(registro, campo)
        if registro.exc_info:
            datos["error"] = self.formatException(registro.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def configurar(nivel: int = logging.INFO) -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJson())
    logging.basicConfig(level=nivel, handlers=[manejador], force=True)
