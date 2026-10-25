import pytest

from ivostock.ingesta.coeficiente import calcular


def estado(cantidad, stock=10):
    return {f"sku{i:05d}": stock for i in range(cantidad)}


def test_corridas_identicas_no_son_sospechosas():
    previo = estado(1000)
    senales = calcular(previo, dict(previo))
    assert senales.p == 0
    assert not senales.sospechosa


def test_sin_estado_previo_no_hay_base_de_comparacion():
    assert calcular({}, estado(10)).p == 0


def test_faltante_por_encima_del_5_por_ciento_entra_en_cuarentena():
    previo = estado(1000)
    nuevo = dict(list(previo.items())[60:])  # faltan 60 de 1000 = 6 %
    senales = calcular(previo, nuevo)
    assert senales.D == pytest.approx(0.06)
    assert senales.sospechosa


def test_faltante_por_debajo_del_5_por_ciento_se_acepta():
    previo = estado(1000)
    nuevo = dict(list(previo.items())[40:])  # 4 %
    assert not calcular(previo, nuevo).sospechosa


def test_ceros_nuevos_por_encima_del_12_5_por_ciento_entran_en_cuarentena():
    previo = estado(1000)
    nuevo = dict(previo)
    for sku in list(previo)[:130]:  # 13 %
        nuevo[sku] = 0
    senales = calcular(previo, nuevo)
    assert senales.Z == pytest.approx(0.13)
    assert senales.sospechosa


def test_los_ausentes_no_cuentan_como_ceros_nuevos():
    previo = estado(100)
    nuevo = dict(list(previo.items())[1:])
    assert calcular(previo, nuevo).Z == 0


def test_feed_vacio_satura_la_senal_de_faltantes():
    senales = calcular(estado(100), {})
    assert senales.d == 1
    assert senales.sospechosa
