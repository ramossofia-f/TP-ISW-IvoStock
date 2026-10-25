import pytest

from ivostock.ingesta.fuente import descargar
from ivostock.ingesta.normalizacion import normalizar


def test_sku_se_conserva_como_texto():
    resultado = normalizar(b"SKU;stock\n9782444846X31;3\n0012345678901;7\n")
    assert resultado.stock == {"9782444846X31": 3, "0012345678901": 7}


def test_stock_en_blanco_vale_cero():
    resultado = normalizar(b"SKU;stock\nISBN-X;\n")
    assert resultado.stock == {"ISBN-X": 0}
    assert resultado.discarded == []


def test_duplicado_registra_la_ocurrencia_que_reemplaza():
    resultado = normalizar(b"SKU;stock\nA;3\nA;9\nA;7\n")
    assert resultado.stock == {"A": 7}
    assert resultado.discarded == [
        {"line": 2, "reason": "duplicate"},
        {"line": 3, "reason": "duplicate"},
    ]
    assert resultado.error_rate == 0


def test_duplicado_invalido_no_reemplaza_el_ultimo_valido():
    resultado = normalizar(b"SKU;stock\nA;8\nA;invalid\n")
    assert resultado.stock == {"A": 8}
    assert resultado.discarded == [{"line": 3, "reason": "quantity"}]


def test_columnas_extra_y_filas_vacias_son_descartes():
    resultado = normalizar(b"SKU;stock\nA;1;extra\n\nB;3\n")
    assert resultado.stock == {"B": 3}
    assert resultado.lines == 3
    assert resultado.error_rate == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    "raw", [b"sku;stock\nA;1\n", b"SKU,stock\nA,1\n", b"A;1\n", b"\xef\xbb\xbfSKU;stock\nA;1\n"]
)
def test_encabezado_fijo_obligatorio(raw):
    with pytest.raises(ValueError):
        normalizar(raw)


def test_otra_codificacion_no_se_acepta_como_utf8():
    with pytest.raises(UnicodeDecodeError):
        normalizar("SKU;stock\nISBN-ñ;1\n".encode("cp1252"))


def test_proveedor_solo_admite_http():
    with pytest.raises(ValueError, match="URL HTTP"):
        descargar("data/feeds/demo.csv")
