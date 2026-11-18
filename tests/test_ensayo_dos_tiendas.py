import importlib.util
from pathlib import Path

import pytest

ruta = Path(__file__).resolve().parents[1] / "scripts" / "ensayo_dos_tiendas.py"
spec = importlib.util.spec_from_file_location("ensayo_dos_tiendas", ruta)
ensayo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ensayo)


def fila(**cambios):
    base = {
        "store_id": "T1",
        "revisions": 1000,
        "superseded": 0,
        "pending": 0,
        "unknown_duration": 0,
        "samples": 1000,
        "p95_seconds": 16 * 60,
        "p99_seconds": 17 * 60,
        "oldest_pending_seconds": None,
    }
    return {**base, **cambios}


def test_cumple_con_todo_medido_y_bajo_los_maximos():
    assert ensayo.veredicto(fila(), 1000) == {"cumple": True, "motivos": []}


@pytest.mark.parametrize(
    "cambios,motivo",
    [
        ({"pending": 3}, "3 pendientes"),
        ({"unknown_duration": 2}, "2 sin duración verificable"),
        ({"samples": 999}, "999 muestras de 1000 esperadas"),
        ({"p95_seconds": 30 * 60}, "p95 fuera de objetivo"),
        ({"p99_seconds": 60 * 60}, "p99 fuera de objetivo"),
        ({"p95_seconds": None, "p99_seconds": None, "samples": 0}, "p95 fuera de objetivo"),
    ],
)
def test_no_cumple_si_falta_medir_o_supera_el_maximo(cambios, motivo):
    resultado = ensayo.veredicto(fila(**cambios), 1000)
    assert not resultado["cumple"] and motivo in resultado["motivos"]


def test_sin_cantidad_esperada_no_exige_muestras_exactas():
    assert ensayo.veredicto(fila(samples=412), None)["cumple"]


@pytest.mark.parametrize(
    "uso,mib",
    [("12.5MiB / 7.6GiB", 12.5), ("1.5GiB / 7.6GiB", 1536), ("512KiB / 1GiB", 0.5)],
)
def test_memoria_en_mib(uso, mib):
    assert ensayo.memoria_mib(uso) == pytest.approx(mib)


def test_reporte_muestra_veredicto_cambios_y_recursos():
    corrida = {
        "numero": 1,
        "run_id": 1,
        "sku": 10000,
        "segundos_hasta_drenar": 1020.0,
        "tiendas": {"T1": fila(), "T2": fila(store_id="T2", pending=1)},
        "veredicto": {
            "T1": ensayo.veredicto(fila(), 1000),
            "T2": ensayo.veredicto(fila(store_id="T2", pending=1), 1000),
        },
    }
    texto = ensayo.reporte(
        {
            "ejecutado": "2026-11-18T12:00:00+00:00",
            "fuente": "feed sintético",
            "tiendas": ["T1", "T2"],
            "corridas": [corrida],
            "maquina": {
                "sistema": "Linux",
                "docker": "29",
                "cpus_docker": 4,
                "memoria_docker_gib": 8,
            },
            "recursos": {
                "publish": {
                    "muestras": 50,
                    "cpu_promedio_pct": 2.5,
                    "cpu_maximo_pct": 9.0,
                    "memoria_maxima_mib": 80.0,
                },
                "init": {
                    "muestras": 1,
                    "cpu_promedio_pct": 99.6,
                    "cpu_maximo_pct": 99.6,
                    "memoria_maxima_mib": 66.2,
                },
            },
        }
    )
    assert "| 1 | T1 | 1000 | 16,0 | 17,0 | 0 | 0 | cumple |" in texto
    assert "| 1 | T2 | 1000 | 16,0 | 17,0 | 1 | 0 | no cumple: 1 pendientes |" in texto
    assert "| 1 | 10000 | 2000 | 17,0 |" in texto
    assert "| `publish` | 2,5 | 9,0 | 80,0 |" in texto
    assert "`init` |" not in texto


@pytest.mark.parametrize(
    "antes,despues,esperado",
    [
        ((0, 0), (30, 30), 0),
        ((0, 0), (85, 30), 0),
        ((0, 0), (990, 30), 960),
    ],
)
def test_detecta_suspension_por_diferencia_de_relojes(antes, despues, esperado):
    assert ensayo.suspension(antes, despues) == esperado


def test_evidencia_con_suspension_no_genera_reporte(tmp_path, monkeypatch):
    import json

    monkeypatch.chdir(tmp_path)
    evidencia = tmp_path / "evidencia.json"
    evidencia.write_text(
        json.dumps({"fuente": "inventario real", "suspensiones": [{"segundos": 960}]}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as salida:
        ensayo.main(["--reporte-desde", str(evidencia)])
    assert "suspendido 16 minutos" in str(salida.value)
    assert not (tmp_path / "docs").exists()
