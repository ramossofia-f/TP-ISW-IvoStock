"""Entrena y evalúa el detector de corridas defectuosas (ADR-0015).

Uso: uv run --group ml python scripts/ml_entrenar.py [--semilla 15] [--base data/feeds/celesa.csv]

Genera tres conjuntos disjuntos con el generador (entrenamiento, validación y prueba), entrena una
regresión logística, fija el umbral en validación y evalúa en prueba contra la guarda. Escribe
`src/ivostock/ml/modelo.json` y `docs/entregas/ML-EVALUACION.md`. La misma semilla produce los
mismos archivos.
"""

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

from ivostock.generador.feeds import leer_base
from ivostock.ml.datos import ESCENARIOS, conjunto
from ivostock.ml.modelo import Modelo, cuarentena
from ivostock.ml.variables import NOMBRES

root = Path(__file__).resolve().parents[1]
MODELO = root / "src" / "ivostock" / "ml" / "modelo.json"
REPORTE = root / "docs" / "entregas" / "ML-EVALUACION.md"
# Presupuesto de falsas cuarentenas que el modelo puede agregar a las corridas normales que la
# guarda acepta.
PRESUPUESTO = 0.01
DECIMALES = 10


def matriz(ejemplos):
    x = np.array([[e.variables[n] for n in NOMBRES] for e in ejemplos])
    y = np.array([e.etiqueta for e in ejemplos])
    return x, y


def entrenar(ejemplos):
    x, y = matriz(ejemplos)
    medias = x.mean(axis=0)
    # Una variable constante no aporta; escala 1 evita dividir por cero.
    escalas = np.where(x.std(axis=0) > 0, x.std(axis=0), 1.0)
    clasificador = LogisticRegression(class_weight="balanced", max_iter=1000)
    clasificador.fit((x - medias) / escalas, y)
    return medias, escalas, clasificador.coef_[0], clasificador.intercept_[0]


def elegir_umbral(modelo, ejemplos):
    """Menor umbral que agrega a lo sumo `PRESUPUESTO` de cuarentenas a normales aceptadas."""
    puntajes = sorted(
        modelo.puntaje(e.variables) for e in ejemplos if e.etiqueta == 0 and not e.guarda
    )
    permitidas = int(len(puntajes) * PRESUPUESTO)
    return puntajes[len(puntajes) - 1 - permitidas] if puntajes else 0.5


def evaluar(modelo, ejemplos):
    filas = {}
    for escenario in ESCENARIOS:
        grupo = [e for e in ejemplos if e.escenario == escenario]
        guarda = sum(e.guarda for e in grupo) / len(grupo)
        combinado = sum(
            cuarentena(e.guarda, modelo.puntaje(e.variables), modelo.umbral) is not None
            for e in grupo
        ) / len(grupo)
        filas[escenario] = {
            "etiqueta": ESCENARIOS[escenario][0],
            "ejemplos": len(grupo),
            "cuarentena_guarda": round(guarda, 4),
            "cuarentena_combinada": round(combinado, 4),
        }
    return filas


def evaluacion(modelo, ejemplos):
    filas = evaluar(modelo, ejemplos)
    return {"escenarios": filas, "defectuosas": resumen(filas, 1), "normales": resumen(filas, 0)}


def resumen(filas, etiqueta):
    grupo = [f for f in filas.values() if f["etiqueta"] == etiqueta]
    total = sum(f["ejemplos"] for f in grupo)
    return {
        clave: round(sum(f[clave] * f["ejemplos"] for f in grupo) / total, 4)
        for clave in ("cuarentena_guarda", "cuarentena_combinada")
    }


def decimal(valor, formato):
    return format(valor, formato).replace(".", ",")


def tabla(evaluacion):
    lineas = ["| Escenario | Tipo | Guarda | Guarda + modelo |", "|---|---|---|---|"]
    for nombre, fila in evaluacion["escenarios"].items():
        tipo = "defectuosa" if fila["etiqueta"] else "normal"
        lineas.append(
            f"| `{nombre}` | {tipo} | {decimal(fila['cuarentena_guarda'], '.1%')} "
            f"| {decimal(fila['cuarentena_combinada'], '.1%')} |"
        )
    for nombre in ("defectuosas", "normales"):
        total = evaluacion[nombre]
        lineas.append(
            f"| **Todas las {nombre}** | | {decimal(total['cuarentena_guarda'], '.1%')} "
            f"| {decimal(total['cuarentena_combinada'], '.1%')} |"
        )
    return lineas


def reporte(datos, real=None):
    lineas = [
        "# Evaluación del detector de corridas defectuosas",
        "",
        "Generado por `scripts/ml_entrenar.py` "
        "([ADR-0015](../adr/0015-detector-de-feeds-anomalos.md)). Los escenarios y sus etiquetas "
        "son sintéticos: estas cifras no acreditan el comportamiento con un proveedor real.",
        "",
        "En corridas defectuosas, la proporción en cuarentena es el recall; en normales, la tasa "
        "de falsas cuarentenas. «Guarda + modelo» es la decisión combinada: el modelo sólo agrega "
        "cuarentenas.",
        "",
        "## Inventarios sintéticos",
        "",
        f"Modelo `{datos['version']}`, semilla {datos['semilla']}, "
        f"{datos['por_escenario']} ejemplos por escenario y conjunto, umbral "
        f"{decimal(datos['umbral'], '.4f')}. El conjunto de prueba es disjunto del de "
        "entrenamiento y del de validación, donde se fija el umbral.",
        "",
        *tabla(datos["evaluacion"]),
    ]
    if real:
        lineas += [
            "",
            "## Escenarios sobre el inventario real",
            "",
            f"Los mismos escenarios aplicados sobre el inventario preparado de Celesa "
            f"({real['skus']} SKU, SHA-256 `{real['sha256'][:12]}`), {real['por_escenario']} "
            "ejemplos por escenario. El archivo queda fuera de Git; se versiona sólo este resumen. "
            "Los SKU y las cantidades son reales; el orden del archivo lo fija el generador (por SKU) y "
            "las alteraciones son sintéticas.",
            "",
            *tabla(real["evaluacion"]),
        ]
    lineas += [
        "",
        "## Coeficientes",
        "",
        "Sobre variables estandarizadas: a mayor valor absoluto, más peso.",
        "",
        "| Variable | Coeficiente |",
        "|---|---|",
        *(f"| `{n}` | {decimal(c, '+.3f')} |" for n, c in zip(NOMBRES, datos["coeficientes"])),
        "",
    ]
    return "\n".join(lineas)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=int, default=15)
    parser.add_argument("--por-escenario", type=int, default=300)
    parser.add_argument(
        "--base", type=Path, help="Inventario real preparado (SKU;stock) para evaluar además sobre él"
    )
    parser.add_argument("--por-escenario-real", type=int, default=30)
    args = parser.parse_args(argv)
    entrenamiento, validacion, prueba = (
        conjunto(args.semilla * 3 + parte, args.por_escenario) for parte in range(3)
    )
    medias, escalas, coeficientes, intercepto = entrenar(entrenamiento)

    def redondear(valores):
        return [round(float(v), DECIMALES) for v in valores]

    datos = {
        "variables": list(NOMBRES),
        "medias": redondear(medias),
        "escalas": redondear(escalas),
        "coeficientes": redondear(coeficientes),
        "intercepto": round(float(intercepto), DECIMALES),
        "semilla": args.semilla,
        "por_escenario": args.por_escenario,
    }
    datos["version"] = hashlib.sha256(json.dumps(datos, sort_keys=True).encode()).hexdigest()[:12]
    provisorio = Modelo(
        datos["version"],
        tuple(datos["medias"]),
        tuple(datos["escalas"]),
        tuple(datos["coeficientes"]),
        datos["intercepto"],
        0.5,
    )
    datos["umbral"] = round(elegir_umbral(provisorio, validacion), DECIMALES)
    modelo = dataclasses.replace(provisorio, umbral=datos["umbral"])
    datos["evaluacion"] = evaluacion(modelo, prueba)
    MODELO.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    real = None
    if args.base:
        # El modelo no depende del inventario real: sólo se evalúa sobre él.
        contenido = args.base.read_bytes()
        base = leer_base(contenido)
        real = {
            "skus": len(base),
            "sha256": hashlib.sha256(contenido).hexdigest(),
            "por_escenario": args.por_escenario_real,
            "evaluacion": evaluacion(
                modelo, conjunto(args.semilla * 3 + 3, args.por_escenario_real, base)
            ),
        }
    REPORTE.write_text(reporte(datos, real), encoding="utf-8")
    print(json.dumps({"sintetico": datos["evaluacion"], "real": real}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
