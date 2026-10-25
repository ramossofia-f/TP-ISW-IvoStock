"""Una corrida de ingesta de punta a punta.

Descarga -> snapshot crudo -> normalización -> coeficiente de CU-07 -> estado vigente.
Una corrida en cuarentena no modifica el estado vigente ni genera trabajo (RF-28).
"""

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from ivostock.ingesta import coeficiente, snapshots
from ivostock.ingesta.normalizacion import normalizar
from ivostock.ingesta.proveedor import ConfigProveedor
from ivostock.ingesta.repositorio import (
    ACEPTADA,
    CUARENTENA,
    FALLIDA,
    REPETIDA,
    Corrida,
    Repositorio,
)

UMBRAL_ALERTA_PARSEO = 0.10  # RF-44: alerta sin detener la corrida

log = logging.getLogger("ivostock.ingesta")


def ejecutar_corrida(
    config: ConfigProveedor,
    *,
    descargar: Callable[[str], bytes],
    almacen: snapshots.AlmacenSnapshots,
    repositorio: Repositorio,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Corrida:
    corrida = Corrida(
        id=str(uuid.uuid4()), proveedor_id=config.id, iniciada=ahora(), estado=FALLIDA
    )
    traza = {"corrida_id": corrida.id, "proveedor_id": config.id}

    try:
        crudo = descargar(config.origen())
    except Exception as error:
        # El mensaje no incluye la URL: puede llevar credenciales (RNF-07).
        corrida.motivo = f"descarga fallida: {type(error).__name__}"
        log.error("No se pudo descargar el feed", extra={**traza, "estado": FALLIDA})
        repositorio.guardar_corrida(corrida, [], None)
        return corrida

    corrida.sha256 = hashlib.sha256(crudo).hexdigest()
    corrida.snapshot_clave = snapshots.clave(config.id, corrida.id, corrida.iniciada)
    almacen.guardar(corrida.snapshot_clave, crudo, corrida.sha256)

    try:
        normalizada = normalizar(crudo, config)
    except ValueError as error:
        corrida.motivo = f"normalización fallida: {error}"
        log.error("No se pudo normalizar la corrida", extra={**traza, "estado": FALLIDA})
        repositorio.guardar_corrida(corrida, [], None)
        return corrida

    corrida.filas = normalizada.filas
    corrida.errores_parseo = normalizada.errores_parseo
    corrida.duplicados = normalizada.duplicados
    corrida.encoding = normalizada.encoding

    if not normalizada.stock:
        corrida.motivo = "la corrida no tiene ninguna fila válida"
        log.error("Corrida vacía", extra={**traza, "estado": FALLIDA})
        repositorio.guardar_corrida(corrida, normalizada.descartes, None)
        return corrida

    if normalizada.tasa_error > UMBRAL_ALERTA_PARSEO:
        log.warning(
            "Más del 10 %% de las filas con error de parseo (%.1f %%)",
            normalizada.tasa_error * 100,
            extra=traza,
        )

    if corrida.sha256 == repositorio.sha_ultima_aceptada(config.id):
        corrida.estado = REPETIDA
        corrida.senal_d = corrida.senal_z = corrida.coeficiente = 0.0
        log.info("Corrida idéntica a la última aceptada", extra={**traza, "estado": REPETIDA})
        repositorio.guardar_corrida(corrida, normalizada.descartes, None)
        return corrida

    senales = coeficiente.calcular(repositorio.estado_vigente(config.id), normalizada.stock)
    corrida.senal_d, corrida.senal_z, corrida.coeficiente = senales.D, senales.Z, senales.p

    if senales.sospechosa:
        corrida.estado = CUARENTENA
        corrida.motivo = f"coeficiente {senales.p:.3f} > 0.5 (D={senales.D:.4f}, Z={senales.Z:.4f})"
        log.warning("Corrida en cuarentena", extra={**traza, "estado": CUARENTENA})
        repositorio.guardar_corrida(corrida, normalizada.descartes, None)
        return corrida

    corrida.estado = ACEPTADA
    repositorio.guardar_corrida(corrida, normalizada.descartes, normalizada.stock)
    log.info(
        "Corrida aceptada: %d SKU en el estado vigente",
        len(normalizada.stock),
        extra={**traza, "estado": ACEPTADA},
    )
    return corrida
