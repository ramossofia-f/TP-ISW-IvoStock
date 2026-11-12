from ivostock.generador.feeds import Parametros, generar
from ivostock.ingesta.normalizacion import normalizar
from ivostock.ml.variables import NOMBRES, calcular_variables


def feed(texto):
    return normalizar(texto.encode())


def test_sin_previo_todas_cero():
    variables = calcular_variables(feed("SKU;stock\n"), feed("SKU;stock\nA;1\n"))
    assert variables == dict.fromkeys(NOMBRES, 0.0)


def test_d_y_z_coinciden_con_la_guarda():
    previo = feed("SKU;stock\nA;5\nB;3\nC;0\nD;2\n")
    nuevo = feed("SKU;stock\nA;5\nB;0\nC;0\n")
    variables = calcular_variables(previo, nuevo)
    assert variables["D"] == 0.25
    assert variables["Z"] == 1 / 3
    assert variables["variacion"] == -0.25


def test_truncamiento_concentra_los_ausentes_en_la_cola():
    previo = feed(generar(Parametros(semilla=3, skus=1000)))
    truncado = feed(generar(Parametros(semilla=4, skus=1000, truncar=0.02), previo.stock))
    dispersas = feed(generar(Parametros(semilla=4, skus=1000, bajas=0.02), previo.stock))
    assert calcular_variables(previo, truncado)["cola"] == 1.0
    assert calcular_variables(previo, dispersas)["cola"] < 0.2


def test_errores_y_cambios():
    previo = feed("SKU;stock\nA;1\nB;2\nC;3\nD;4\n")
    nuevo = feed("SKU;stock\nA;1\nB;9\nC;3\nD;abc\n")
    variables = calcular_variables(previo, nuevo)
    assert variables["errores"] == 0.25
    assert variables["cambios"] == 1 / 3


def test_ks_es_cero_con_distribuciones_iguales_y_uno_disjuntas():
    previo = feed("SKU;stock\nA;1\nB;2\n")
    assert calcular_variables(previo, feed("SKU;stock\nA;2\nB;1\n"))["ks"] == 0.0
    assert calcular_variables(previo, feed("SKU;stock\nA;7\nB;8\n"))["ks"] == 1.0
