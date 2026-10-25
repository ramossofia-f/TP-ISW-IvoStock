from ivostock.generador.feeds import Parametros, generar, leer_base
from ivostock.ingesta.normalizacion import normalizar
from ivostock.ingesta.proveedor import ConfigProveedor

CONFIG = ConfigProveedor(id="g", separador=";", encabezado=False, col_sku=0, col_stock=1, url="x")


def test_misma_semilla_mismo_feed():
    assert generar(Parametros(semilla=1, skus=500)) == generar(Parametros(semilla=1, skus=500))
    assert generar(Parametros(semilla=1, skus=500)) != generar(Parametros(semilla=2, skus=500))


def test_truncar_corta_la_fraccion_final():
    completo = generar(Parametros(skus=1000)).splitlines()
    truncado = generar(Parametros(skus=1000, truncar=0.25)).splitlines()
    assert len(truncado) == 750
    assert truncado == completo[:750]


def test_ceros_en_masa():
    resultado = normalizar(generar(Parametros(skus=1000, ceros=0.2)).encode(), CONFIG)
    assert sum(1 for v in resultado.stock.values() if v == 0) == 200


def test_filas_corruptas_son_errores_de_parseo():
    resultado = normalizar(generar(Parametros(skus=1000, corruptas=0.05)).encode(), CONFIG)
    assert resultado.errores_parseo == 50


def test_otro_separador_con_encabezado():
    feed = generar(Parametros(skus=10, separador=",", encabezado=True))
    assert feed.splitlines()[0] == "sku,stock"
    config = ConfigProveedor(
        id="g", separador=",", encabezado=True, col_sku="sku", col_stock="stock", url="x"
    )
    assert len(normalizar(feed.encode(), config).stock) == 10


def test_generar_desde_una_base_conserva_sus_skus():
    base = leer_base(b"9780000000001;4\n9780000000002;9\n")
    feed = generar(Parametros(), base)
    assert feed == "9780000000001;4\n9780000000002;9\n"
