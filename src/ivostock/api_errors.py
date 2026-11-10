"""Traducción de errores a respuestas HTTP sin filtrar detalles internos (RNF-10)."""

import logging

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from ivostock.errors import ServiceError

log = logging.getLogger("ivostock.api")


class SafeRoute(APIRoute):
    """Ruta que convierte toda excepción en una respuesta JSON `{"detail": ...}`.

    - `ServiceError` y subclases: su código (404, 409, 422, 502) y su mensaje, que es nuestro.
    - Un `ValueError` cualquiera: 422 con su mensaje, como hace `cli.execute`.
    - Cualquier otra excepción: 500 "Error interno". Se registra sólo el tipo y la ruta: el texto
      de excepciones de SQLAlchemy, httpx o boto puede incluir URLs, SQL o credenciales, y como la
      excepción no llega a Starlette tampoco se imprime su traza.
    """

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request):
            try:
                return await handler(request)
            except (StarletteHTTPException, RequestValidationError):
                raise
            except ServiceError as exc:
                raise HTTPException(exc.status_code, str(exc)) from None
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            except Exception as exc:
                log.error(
                    "Solicitud fallida %s %s",
                    request.method,
                    request.url.path,
                    extra={"component": "api", "status": 500, "error": type(exc).__name__},
                )
                raise HTTPException(500, "Error interno") from None

        return guarded
