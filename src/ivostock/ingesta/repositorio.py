"""Persistencia de proveedores, corridas y estado vigente en la base del motor (ADR-0005)."""

import json
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from typing import Protocol

from ivostock.ingesta.normalizacion import Descarte
from ivostock.ingesta.proveedor import ConfigProveedor

CANAL_CORRIDAS = "corrida_aceptada"

ACEPTADA = "aceptada"
CUARENTENA = "cuarentena"
REPETIDA = "repetida"
FALLIDA = "fallida"


@dataclass
class Corrida:
    id: str
    proveedor_id: str
    iniciada: datetime
    estado: str
    motivo: str | None = None
    filas: int = 0
    errores_parseo: int = 0
    duplicados: int = 0
    senal_d: float | None = None
    senal_z: float | None = None
    coeficiente: float | None = None
    snapshot_clave: str | None = None
    sha256: str | None = None
    encoding: str | None = None


class Repositorio(Protocol):
    def registrar_proveedor(self, config: ConfigProveedor, validado_en: datetime) -> None: ...

    def proveedor_validado(self, proveedor_id: str) -> bool: ...

    def estado_vigente(self, proveedor_id: str) -> dict[str, int]: ...

    def sha_ultima_aceptada(self, proveedor_id: str) -> str | None: ...

    def guardar_corrida(
        self, corrida: Corrida, descartes: list[Descarte], estado: dict[str, int] | None
    ) -> None:
        """Guarda la corrida y, si `estado` no es None, reemplaza el estado vigente y avisa al
        comparador. Todo en una sola transacción."""

    def ultimas_corridas(self, proveedor_id: str, limite: int) -> list[Corrida]: ...


class RepositorioMemoria:
    """Implementación en memoria para tests. Respeta la misma semántica que PostgreSQL."""

    def __init__(self) -> None:
        self.proveedores: dict[str, datetime] = {}
        self.corridas: list[Corrida] = []
        self.descartes: dict[str, list[Descarte]] = {}
        self.estados: dict[str, dict[str, int]] = {}
        self.avisos: list[str] = []

    def registrar_proveedor(self, config: ConfigProveedor, validado_en: datetime) -> None:
        self.proveedores[config.id] = validado_en

    def proveedor_validado(self, proveedor_id: str) -> bool:
        return proveedor_id in self.proveedores

    def estado_vigente(self, proveedor_id: str) -> dict[str, int]:
        return dict(self.estados.get(proveedor_id, {}))

    def sha_ultima_aceptada(self, proveedor_id: str) -> str | None:
        for corrida in reversed(self.corridas):
            if corrida.proveedor_id == proveedor_id and corrida.estado == ACEPTADA:
                return corrida.sha256
        return None

    def guardar_corrida(
        self, corrida: Corrida, descartes: list[Descarte], estado: dict[str, int] | None
    ) -> None:
        self.corridas.append(corrida)
        self.descartes[corrida.id] = list(descartes)
        if estado is not None:
            self.estados[corrida.proveedor_id] = dict(estado)
            self.avisos.append(corrida.id)

    def ultimas_corridas(self, proveedor_id: str, limite: int) -> list[Corrida]:
        propias = [c for c in self.corridas if c.proveedor_id == proveedor_id]
        return list(reversed(propias))[:limite]


class RepositorioPostgres:
    def __init__(self, url: str) -> None:
        import psycopg

        # autocommit: las lecturas no dejan transacciones abiertas y cada `transaction()` es una
        # transacción real que se confirma al salir del bloque, no un savepoint.
        self.conexion = psycopg.connect(url, autocommit=True)

    def crear_esquema(self) -> None:
        sql = resources.files("ivostock.db").joinpath("esquema.sql").read_text(encoding="utf-8")
        with self.conexion.transaction():
            self.conexion.execute(sql)

    def registrar_proveedor(self, config: ConfigProveedor, validado_en: datetime) -> None:
        with self.conexion.transaction():
            self.conexion.execute(
                """
                INSERT INTO proveedores (id, config, prioridad, validado_en)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET config = EXCLUDED.config, prioridad = EXCLUDED.prioridad,
                    validado_en = EXCLUDED.validado_en
                """,
                (config.id, json.dumps(config.como_dict()), config.prioridad, validado_en),
            )

    def proveedor_validado(self, proveedor_id: str) -> bool:
        fila = self.conexion.execute(
            "SELECT validado_en IS NOT NULL FROM proveedores WHERE id = %s", (proveedor_id,)
        ).fetchone()
        return bool(fila and fila[0])

    def estado_vigente(self, proveedor_id: str) -> dict[str, int]:
        filas = self.conexion.execute(
            "SELECT sku, stock FROM estado_vigente WHERE proveedor_id = %s", (proveedor_id,)
        ).fetchall()
        return dict(filas)

    def sha_ultima_aceptada(self, proveedor_id: str) -> str | None:
        fila = self.conexion.execute(
            """
            SELECT sha256 FROM corridas WHERE proveedor_id = %s AND estado = %s
            ORDER BY iniciada DESC LIMIT 1
            """,
            (proveedor_id, ACEPTADA),
        ).fetchone()
        return fila[0] if fila else None

    def guardar_corrida(
        self, corrida: Corrida, descartes: list[Descarte], estado: dict[str, int] | None
    ) -> None:
        with self.conexion.transaction(), self.conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO corridas (id, proveedor_id, iniciada, estado, motivo, filas,
                    errores_parseo, duplicados, senal_d, senal_z, coeficiente, snapshot_clave,
                    sha256, encoding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    corrida.id, corrida.proveedor_id, corrida.iniciada, corrida.estado,
                    corrida.motivo, corrida.filas, corrida.errores_parseo, corrida.duplicados,
                    corrida.senal_d, corrida.senal_z, corrida.coeficiente,
                    corrida.snapshot_clave, corrida.sha256, corrida.encoding,
                ),
            )
            with cursor.copy(
                "COPY corrida_descartes (corrida_id, linea, motivo, contenido) FROM STDIN"
            ) as copia:
                for descarte in descartes:
                    copia.write_row(
                        (corrida.id, descarte.linea, descarte.motivo, descarte.contenido)
                    )
            if estado is None:
                return
            cursor.execute(
                "DELETE FROM estado_vigente WHERE proveedor_id = %s", (corrida.proveedor_id,)
            )
            with cursor.copy(
                "COPY estado_vigente (proveedor_id, sku, stock, corrida_id) FROM STDIN"
            ) as copia:
                for sku, stock in estado.items():
                    copia.write_row((corrida.proveedor_id, sku, stock, corrida.id))
            cursor.execute("SELECT pg_notify(%s, %s)", (CANAL_CORRIDAS, corrida.id))

    def ultimas_corridas(self, proveedor_id: str, limite: int) -> list[Corrida]:
        filas = self.conexion.execute(
            """
            SELECT id::text, proveedor_id, iniciada, estado, motivo, filas, errores_parseo,
                duplicados, senal_d, senal_z, coeficiente, snapshot_clave, sha256, encoding
            FROM corridas WHERE proveedor_id = %s ORDER BY iniciada DESC LIMIT %s
            """,
            (proveedor_id, limite),
        ).fetchall()
        return [Corrida(*fila) for fila in filas]

    def cerrar(self) -> None:
        self.conexion.close()
