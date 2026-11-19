import importlib.util
import sys
from collections import Counter
from pathlib import Path

import pytest

scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("ensayo_consultas", scripts / "ensayo_consultas.py")
ensayo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ensayo)

SKUS = {"T1": ["A", "B"], "T2": ["C"]}


def plan(semilla=9, segundos=1800):
    return ensayo.plan(semilla, 5, segundos, ["T1", "T2"], SKUS, 7, 1000)


def test_plan_respeta_el_protocolo_del_srd():
    consultas = plan()
    assert len(consultas) == 9000
    assert Counter(c[2] for c in consultas) == {
        "listado": 4500,
        "sku": 2250,
        "corridas": 1125,
        "fallas": 1125,
    }
    # Cada operador consulta exactamente una vez por segundo.
    for operador in range(5):
        segundos = [c[0] for c in consultas if c[1] == operador]
        assert len(segundos) == 1800
        assert all(b - a == pytest.approx(1) for a, b in zip(segundos, segundos[1:]))


def test_plan_es_determinista_y_usa_parametros_validos():
    assert plan() == plan()
    assert plan() != plan(semilla=10)
    for _, _, tipo, ruta, parametros in plan(segundos=60):
        if tipo == "listado":
            assert ruta == "/links" and parametros["limit"] == 100
            assert parametros["offset"] % 100 == 0 and 0 <= parametros["offset"] <= 900
        elif tipo == "sku":
            assert ruta == "/providers/7/suggestions"
            assert parametros["sku"] in SKUS[parametros["store"]]
        elif tipo == "corridas":
            assert ruta == "/runs"
        else:
            assert ruta == "/links/summary"


@pytest.mark.parametrize("p,esperado", [(0.5, 50), (0.95, 95), (0.99, 99), (1.0, 100), (0.001, 1)])
def test_percentil_por_rango_mas_cercano(p, esperado):
    assert ensayo.percentil(list(range(100, 0, -1)), p) == esperado
    assert ensayo.percentil([], p) is None


def resultados(latencias, estado=200):
    return [
        {"segundo": i, "operador": 0, "tipo": "listado", "estado": estado, "latencia": latencia}
        for i, latencia in enumerate(latencias)
    ]


def test_cumple_con_todas_las_consultas_exitosas_y_p95_bajo():
    resumen = ensayo.resumir(resultados([0.1] * 100))
    assert resumen["total"]["p95"] == 0.1 and resumen["sku"]["consultas"] == 0
    assert ensayo.veredicto(resumen, 100) == {"cumple": True, "motivos": []}


@pytest.mark.parametrize(
    "datos,esperadas,motivo",
    [
        (resultados([0.1] * 99), 100, "99 consultas de 100 programadas"),
        (
            resultados([0.1] * 98) + resultados([10.0] * 2, "ReadTimeout"),
            100,
            "2 consultas sin respuesta exitosa",
        ),
        (resultados([0.1] * 90 + [2.5] * 10), 100, "p95 fuera de objetivo"),
    ],
)
def test_no_cumple_si_faltan_consultas_hay_errores_o_p95_alto(datos, esperadas, motivo):
    resultado = ensayo.veredicto(ensayo.resumir(datos), esperadas)
    assert not resultado["cumple"] and motivo in resultado["motivos"]


def test_reporte_muestra_resultado_tipos_y_motor():
    resumen = ensayo.resumir(resultados([0.05] * 50))
    texto = ensayo.reporte(
        {
            "ejecutado": "2026-11-19T12:00:00+00:00",
            "fuente": "feed sintético",
            "minutos": 30,
            "vinculos": 2000,
            "resumen": resumen,
            "veredicto": ensayo.veredicto(resumen, 50),
            "motor": {
                "corridas": [{"id": 3, "status": "accepted"}],
                "publicaciones_aplicadas": 900,
            },
            "maquina": {
                "sistema": "Linux",
                "docker": "29",
                "cpus_docker": 4,
                "memoria_docker_gib": 8,
            },
            "recursos": {},
        }
    )
    assert "**Resultado: cumple.**" in texto
    assert "| **Total** | 50 | 0 | 50 | 50 | 50 | 50 |" in texto
    assert "Corridas: #3 accepted. Publicaciones aplicadas durante la medición: 900." in texto
