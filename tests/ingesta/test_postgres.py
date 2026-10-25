"""Integración con PostgreSQL real. Corre en el CI y localmente si se define
IVOSTOCK_TEST_DATABASE_URL apuntando a una base descartable."""

import os
from datetime import UTC, datetime

import pytest

from ivostock.generador.feeds import Parametros, generar
from ivostock.ingesta.proveedor import ConfigProveedor
from ivostock.ingesta.repositorio import CANAL_CORRIDAS, RepositorioPostgres
from ivostock.ingesta.servicio import ejecutar_corrida
from ivostock.ingesta.snapshots import AlmacenMemoria

URL = os.environ.get("IVOSTOCK_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integracion,
    pytest.mark.skipif(not URL, reason="sin IVOSTOCK_TEST_DATABASE_URL"),
]
CONFIG = ConfigProveedor(
    id="celesa", separador=";", encabezado=False, col_sku=0, col_stock=1, url="x"
)


@pytest.fixture
def repositorio():
    repo = RepositorioPostgres(URL)
    with repo.conexion.transaction():
        repo.conexion.execute(
            "DROP TABLE IF EXISTS estado_vigente, corrida_descartes, corridas, proveedores"
        )
    repo.crear_esquema()
    repo.registrar_proveedor(CONFIG, datetime.now(UTC))
    yield repo
    repo.cerrar()


def correr(repositorio, contenido: str):
    return ejecutar_corrida(
        CONFIG,
        descargar=lambda _: contenido.encode(),
        almacen=AlmacenMemoria(),
        repositorio=repositorio,
    )


def test_corrida_aceptada_reemplaza_el_estado_y_notifica(repositorio):
    import psycopg

    avisos: list[str] = []
    with psycopg.connect(URL, autocommit=True) as escucha:
        escucha.add_notify_handler(lambda aviso: avisos.append(aviso.payload))
        escucha.execute(f"LISTEN {CANAL_CORRIDAS}")
        corrida = correr(repositorio, "9780000000001;5\n9780000000002;3\n")
        escucha.execute("SELECT 1")  # procesa los avisos pendientes
    assert corrida.estado == "aceptada"
    assert repositorio.estado_vigente("celesa") == {"9780000000001": 5, "9780000000002": 3}
    assert avisos == [corrida.id]



def test_corrida_aceptada_reemplaza_el_estado_completo(repositorio):
    base = {f"97800000{i:05d}": 10 for i in range(100)}
    correr(repositorio, "".join(f"{sku};{v}\n" for sku, v in base.items()))
    nuevo = dict(base)
    del nuevo["9780000000000"]  # falta 1 de 100: se acepta y pasa a valer cero
    nuevo["9780000000001"] = 4
    corrida = correr(repositorio, "".join(f"{sku};{v}\n" for sku, v in nuevo.items()))
    assert corrida.estado == "aceptada"
    assert repositorio.estado_vigente("celesa") == nuevo


def test_cuarentena_no_modifica_el_estado_vigente(repositorio):
    correr(repositorio, generar(Parametros(skus=1000)))
    antes = repositorio.estado_vigente("celesa")
    corrida = correr(repositorio, generar(Parametros(skus=1000, truncar=0.5)))
    assert corrida.estado == "cuarentena"
    assert repositorio.estado_vigente("celesa") == antes
    ultimas = repositorio.ultimas_corridas("celesa", 5)
    assert [c.estado for c in ultimas] == ["cuarentena", "aceptada"]


def test_descartes_se_persisten(repositorio):
    corrida = correr(repositorio, "9780000000001;-1\n" + generar(Parametros(skus=10)))
    filas = repositorio.conexion.execute(
        "SELECT motivo FROM corrida_descartes WHERE corrida_id = %s", (corrida.id,)
    ).fetchall()
    assert filas == [("stock_negativo",)]


def test_la_corrida_queda_confirmada_para_otras_conexiones(repositorio):
    import psycopg

    corrida = correr(repositorio, "9780000000001;5\n")
    with psycopg.connect(URL) as otra:
        fila = otra.execute("SELECT estado FROM corridas WHERE id = %s", (corrida.id,)).fetchone()
    assert fila == ("aceptada",)
