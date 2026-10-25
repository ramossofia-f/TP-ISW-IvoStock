"""Corrida de punta a punta con almacenes en memoria, incluidos los caminos de falla de P2."""

import logging
from datetime import UTC, datetime, timedelta

import pytest

from ivostock.generador.feeds import Parametros, generar
from ivostock.ingesta.proveedor import ConfigProveedor
from ivostock.ingesta.repositorio import RepositorioMemoria
from ivostock.ingesta.servicio import ejecutar_corrida
from ivostock.ingesta.snapshots import AlmacenMemoria, SnapshotExistente

SECRETO = "https://feed.example/stock?usuario=u&clave=SUPERSECRETA"
CONFIG = ConfigProveedor(
    id="celesa", separador=";", encabezado=False, col_sku=0, col_stock=1, url=SECRETO
)
BASE = Parametros(semilla=7, skus=2000)


class Entorno:
    def __init__(self):
        self.almacen = AlmacenMemoria()
        self.repositorio = RepositorioMemoria()
        self.reloj = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)

    def correr(self, contenido: str | bytes | Exception):
        def descargar(_origen):
            if isinstance(contenido, Exception):
                raise contenido
            return contenido if isinstance(contenido, bytes) else contenido.encode()

        self.reloj += timedelta(minutes=30)
        return ejecutar_corrida(
            CONFIG,
            descargar=descargar,
            almacen=self.almacen,
            repositorio=self.repositorio,
            ahora=lambda: self.reloj,
        )

    @property
    def vigente(self):
        return self.repositorio.estado_vigente("celesa")


@pytest.fixture
def entorno():
    return Entorno()


def test_primera_corrida_se_acepta_y_avisa_al_comparador(entorno):
    corrida = entorno.correr(generar(BASE))
    assert corrida.estado == "aceptada"
    assert len(entorno.vigente) == 2000
    assert entorno.repositorio.avisos == [corrida.id]


def test_snapshot_crudo_se_guarda_tal_como_llego(entorno):
    feed = generar(BASE)
    corrida = entorno.correr(feed)
    assert entorno.almacen.leer(corrida.snapshot_clave) == feed.encode()


def test_snapshot_no_se_puede_sobrescribir():
    almacen = AlmacenMemoria()
    almacen.guardar("celesa/x.raw", b"a", "sha")
    with pytest.raises(SnapshotExistente):
        almacen.guardar("celesa/x.raw", b"b", "sha")


def test_feed_truncado_queda_en_cuarentena_sin_tocar_el_estado(entorno):
    base = generar(BASE)
    entorno.correr(base)
    antes = entorno.vigente
    truncado = generar(Parametros(semilla=7, skus=2000, truncar=0.3))
    corrida = entorno.correr(truncado)
    assert corrida.estado == "cuarentena"
    assert corrida.senal_d == pytest.approx(0.3)
    assert entorno.vigente == antes
    assert len(entorno.repositorio.avisos) == 1
    assert corrida.snapshot_clave in entorno.almacen.objetos


def test_ceros_en_masa_quedan_en_cuarentena(entorno):
    entorno.correr(generar(BASE))
    antes = entorno.vigente
    corrida = entorno.correr(generar(Parametros(semilla=7, skus=2000, ceros=0.2)))
    assert corrida.estado == "cuarentena"
    assert corrida.senal_z == pytest.approx(0.2)
    assert entorno.vigente == antes


def test_sku_ausente_vale_cero_en_el_estado_vigente(entorno):
    entorno.correr("9780000000001;5\n9780000000002;3\n" + generar(BASE))
    corrida = entorno.correr("9780000000001;5\n" + generar(BASE))
    assert corrida.estado == "aceptada"
    assert "9780000000002" not in entorno.vigente  # no figura: vale cero (RF-22)


def test_reprocesar_la_misma_corrida_no_cambia_nada(entorno):
    feed = generar(BASE)
    entorno.correr(feed)
    antes = entorno.vigente
    corrida = entorno.correr(feed)
    assert corrida.estado == "repetida"
    assert entorno.vigente == antes
    assert len(entorno.repositorio.avisos) == 1


def test_deriva_normal_se_acepta(entorno):
    entorno.correr(generar(BASE))
    corrida = entorno.correr(generar(Parametros(semilla=7, skus=2000, deriva=0.05)))
    assert corrida.estado == "aceptada"


def test_descarga_fallida_no_toca_el_estado_ni_loguea_credenciales(entorno, caplog):
    entorno.correr(generar(BASE))
    antes = entorno.vigente
    with caplog.at_level(logging.INFO):
        corrida = entorno.correr(ConnectionError(f"no se pudo conectar a {SECRETO}"))
    assert corrida.estado == "fallida"
    assert entorno.vigente == antes
    assert "SUPERSECRETA" not in caplog.text
    assert "SUPERSECRETA" not in (corrida.motivo or "")


def test_corrida_sin_filas_validas_falla(entorno):
    corrida = entorno.correr("9780000000001;abc\n")
    assert corrida.estado == "fallida"
    assert entorno.vigente == {}


def test_descartes_quedan_registrados(entorno):
    corrida = entorno.correr("9780000000001;abc\n" + generar(BASE))
    descartes = entorno.repositorio.descartes[corrida.id]
    assert [d.motivo for d in descartes] == ["stock_no_numerico"]
