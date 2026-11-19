import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from ivostock.ml.datos import conjunto  # noqa: E402
from ivostock.ml.modelo import Modelo  # noqa: E402

ruta = Path(__file__).resolve().parents[2] / "scripts" / "ml_entrenar.py"
spec = importlib.util.spec_from_file_location("ml_entrenar", ruta)
ml_entrenar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ml_entrenar)


@pytest.fixture
def salidas(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_entrenar, "MODELO", tmp_path / "modelo.json")
    monkeypatch.setattr(ml_entrenar, "REPORTE", tmp_path / "reporte.md")
    return tmp_path


def test_misma_semilla_mismo_modelo_y_reporte(salidas):
    ml_entrenar.main(["--semilla", "2", "--por-escenario", "15"])
    primero = (salidas / "modelo.json").read_bytes(), (salidas / "reporte.md").read_bytes()
    ml_entrenar.main(["--semilla", "2", "--por-escenario", "15"])
    assert ((salidas / "modelo.json").read_bytes(), (salidas / "reporte.md").read_bytes()) == primero


def test_inferencia_en_python_puro_coincide_con_sklearn(salidas):
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    ml_entrenar.main(["--semilla", "2", "--por-escenario", "15"])
    datos = json.loads((salidas / "modelo.json").read_text(encoding="utf-8"))
    modelo = Modelo.cargar(salidas / "modelo.json")
    clasificador = LogisticRegression()
    clasificador.classes_ = np.array([0, 1])
    clasificador.coef_ = np.array([datos["coeficientes"]])
    clasificador.intercept_ = np.array([datos["intercepto"]])
    ejemplos = conjunto(7, 5)
    x, _ = ml_entrenar.matriz(ejemplos)
    esperados = clasificador.predict_proba((x - np.array(datos["medias"])) / np.array(datos["escalas"]))[:, 1]
    for e, esperado in zip(ejemplos, esperados):
        assert modelo.puntaje(e.variables) == pytest.approx(esperado, abs=1e-9)


def test_umbral_respeta_el_presupuesto_de_falsas_cuarentenas(salidas):
    ml_entrenar.main(["--semilla", "2", "--por-escenario", "30"])
    modelo = Modelo.cargar(salidas / "modelo.json")
    validacion = conjunto(2 * 3 + 1, 30)
    normales = [e for e in validacion if e.etiqueta == 0 and not e.guarda]
    agregadas = sum(modelo.puntaje(e.variables) > modelo.umbral for e in normales)
    assert agregadas <= int(len(normales) * ml_entrenar.PRESUPUESTO)
