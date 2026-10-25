import hashlib
import json

import pytest

from ivostock.generador.feeds import Parametros, generar, leer_base, main
from ivostock.ingesta.normalizacion import normalizar


def test_misma_semilla_mismo_feed():
    assert generar(Parametros(semilla=1, skus=500)) == generar(Parametros(semilla=1, skus=500))
    assert generar(Parametros(semilla=1, skus=500)) != generar(Parametros(semilla=2, skus=500))


def test_truncar_conserva_encabezado_y_corta_fraccion_final():
    completo = generar(Parametros(skus=1000)).splitlines()
    truncado = generar(Parametros(skus=1000, truncar=0.25)).splitlines()
    assert truncado[0] == "SKU;stock"
    assert len(truncado) == 751
    assert truncado == completo[:751]


def test_ceros_en_masa():
    resultado = normalizar(generar(Parametros(skus=1000, ceros=0.2)).encode())
    assert sum(quantity == 0 for quantity in resultado.stock.values()) == 200


def test_filas_corruptas_son_errores_de_parseo():
    resultado = normalizar(generar(Parametros(skus=1000, corruptas=0.05)).encode())
    assert resultado.error_rate == 0.05


def test_generar_desde_base_conserva_sku_y_no_muta_entrada():
    base = leer_base(b"SKU;stock\nISBN-X;4\n00123;9\n")
    assert generar(Parametros(), base) == "SKU;stock\n00123;9\nISBN-X;4\n"
    assert base == {"ISBN-X": 4, "00123": 9}


def test_deriva_cambia_exactamente_los_sku_solicitados():
    base = {f"A{n}": 10 for n in range(100)}
    nuevo = normalizar(generar(Parametros(deriva=0.1), base).encode()).stock
    assert sum(base[sku] != quantity for sku, quantity in nuevo.items()) == 10


def test_base_con_duplicados_validos_usa_ultima_ocurrencia():
    assert leer_base(b"SKU;stock\nA;1\nA;3\n") == {"A": 3}


def test_cli_registra_semilla_y_hash_sin_inventario_en_manifiesto(tmp_path):
    target = tmp_path / "synthetic.csv"
    main(["--salida", str(target), "--skus", "20", "--semilla", "19"])
    metadata = json.loads(target.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["synthetic"] is True
    assert metadata["parameters"]["semilla"] == 19
    assert metadata["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.parametrize("fraction", [-0.1, 1.01, float("nan"), float("inf")])
def test_fracciones_invalidas_se_rechazan(fraction):
    with pytest.raises(ValueError):
        Parametros(truncar=fraction)
