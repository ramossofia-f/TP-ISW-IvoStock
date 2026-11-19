import json

import pytest

from ivostock.ingesta.coeficiente import Senales
from ivostock.ml.datos import ESCENARIOS, conjunto, ejemplo
from ivostock.ml.modelo import RUTA, Modelo, cuarentena
from ivostock.ml.variables import NOMBRES


def test_cuarentena_es_monotona():
    # El modelo puede agregar cuarentenas, nunca liberar una de la guarda.
    assert cuarentena(True, 0.0, 0.5) == "guarda"
    assert cuarentena(True, 1.0, 0.5) == "guarda"
    assert cuarentena(False, 0.9, 0.5) == "ml"
    assert cuarentena(False, 0.5, 0.5) is None


def test_modelo_versionado_carga_y_puntua_en_rango():
    modelo = Modelo.cargar()
    datos = json.loads(RUTA.read_text(encoding="utf-8"))
    assert modelo.version == datos["version"] and 0 < modelo.umbral < 1
    for escenario in ESCENARIOS:
        assert 0 <= modelo.puntaje(ejemplo(escenario, 11).variables) <= 1


def test_modelo_con_otras_variables_no_carga(tmp_path):
    datos = json.loads(RUTA.read_text(encoding="utf-8"))
    datos["variables"] = list(reversed(NOMBRES))
    ruta = tmp_path / "modelo.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError):
        Modelo.cargar(ruta)


def test_modelo_versionado_detecta_truncamiento_que_la_guarda_acepta():
    modelo = Modelo.cargar()
    leves = [e for e in conjunto(99, 20) if e.escenario == "truncado_leve" and not e.guarda]
    assert leves
    assert all(cuarentena(e.guarda, modelo.puntaje(e.variables), modelo.umbral) for e in leves)


def test_guarda_del_conjunto_es_la_de_produccion():
    e = ejemplo("depuracion", 5)
    assert e.guarda == Senales(e.variables["D"], e.variables["Z"]).sospechosa


def test_conjunto_reproducible_y_disjunto():
    assert conjunto(1, 3) == conjunto(1, 3)
    assert [e.variables for e in conjunto(1, 3)] != [e.variables for e in conjunto(2, 3)]
