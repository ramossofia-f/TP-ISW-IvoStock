import pytest

from ivostock.ingesta.normalizacion import (
    MAL_FORMADA,
    SKU_DUPLICADO,
    STOCK_NEGATIVO,
    STOCK_NO_NUMERICO,
    normalizar,
)
from ivostock.ingesta.proveedor import ConfigProveedor

CELESA = ConfigProveedor(
    id="celesa", separador=";", encabezado=False, col_sku=0, col_stock=1, url="x"
)


def motivos(resultado):
    return [d.motivo for d in resultado.descartes]


def test_sku_se_conserva_como_texto():
    resultado = normalizar(b"9782444846X31;3\n0012345678901;7\n", CELESA)
    assert resultado.stock == {"9782444846X31": 3, "0012345678901": 7}


def test_stock_en_blanco_vale_cero():
    resultado = normalizar(b"9780000000001;\n", CELESA)
    assert resultado.stock == {"9780000000001": 0}
    assert resultado.descartes == []


def test_stock_con_texto_o_negativo_se_descarta_con_motivo():
    resultado = normalizar(b"9780000000001;abc\n9780000000002;-4\n9780000000003;5\n", CELESA)
    assert resultado.stock == {"9780000000003": 5}
    assert motivos(resultado) == [STOCK_NO_NUMERICO, STOCK_NEGATIVO]
    assert resultado.errores_parseo == 2


def test_sku_duplicado_vale_la_ultima_ocurrencia_y_registra_la_anterior():
    resultado = normalizar(b"9780000000001;3\n9780000000001;9\n", CELESA)
    assert resultado.stock == {"9780000000001": 9}
    assert motivos(resultado) == [SKU_DUPLICADO]
    assert resultado.descartes[0].linea == 1
    assert resultado.errores_parseo == 0


def test_fila_sin_columna_de_stock_es_mal_formada():
    resultado = normalizar(b"9780000000001\n", CELESA)
    assert motivos(resultado) == [MAL_FORMADA]


def test_lineas_vacias_no_cuentan_como_filas():
    resultado = normalizar(b"9780000000001;1\n\n\n9780000000002;2\n", CELESA)
    assert resultado.filas == 2


def test_columnas_por_nombre_con_encabezado():
    config = ConfigProveedor(
        id="otro", separador=",", encabezado=True, col_sku="isbn", col_stock="cantidad", url="x"
    )
    resultado = normalizar(b"cantidad,isbn\n4,9780000000001\n", config)
    assert resultado.stock == {"9780000000001": 4}


def test_columna_inexistente_en_el_encabezado_falla():
    config = ConfigProveedor(
        id="otro", separador=",", encabezado=True, col_sku="isbn", col_stock="stock", url="x"
    )
    with pytest.raises(ValueError):
        normalizar(b"isbn,cantidad\n9780000000001,4\n", config)


def test_bom_y_encoding_alternativo():
    con_bom = normalizar("\ufeff9780000000001;2\n".encode(), CELESA)
    assert con_bom.stock == {"9780000000001": 2}
    latin = normalizar("978000000000ñ;2\n".encode("cp1252"), CELESA)
    assert latin.encoding == "cp1252"


def test_sin_encabezado_no_admite_columnas_por_nombre():
    with pytest.raises(ValueError):
        ConfigProveedor(
            id="x", separador=";", encabezado=False, col_sku="sku", col_stock=1, url="x"
        )
