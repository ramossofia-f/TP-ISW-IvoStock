"""Errores de negocio con su código HTTP.

Heredan de `ValueError`: la CLI sigue mostrando su mensaje (`cli.execute`) y la API los traduce
al código que corresponde (`api_errors.SafeRoute`). Los mensajes son nuestros y nunca incluyen
URLs, credenciales ni texto de excepciones externas.
"""


class ServiceError(ValueError):
    """Dato o petición inválidos (422)."""

    status_code = 422


class NotFound(ServiceError):
    status_code = 404


class Conflict(ServiceError):
    """La petición es válida pero choca con el estado actual (409)."""

    status_code = 409


class UpstreamError(ServiceError):
    """Falla de un sistema externo: la fuente del proveedor o el marketplace (502)."""

    status_code = 502
