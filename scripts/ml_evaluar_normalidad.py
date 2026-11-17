"""Evaluación reproducible y sintética del detector vigente; nunca activa un modelo.

uv run --group ml python scripts/ml_evaluar_normalidad.py
"""

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ivostock.feed import parse, suspicion
from ivostock.generador.feeds import Parametros, generar
from ivostock.ml.config import TrainingConfig
from ivostock.ml.datos import ESCENARIOS
from ivostock.ml.normalidad import NormalityModel
from ivostock.ml.training import fit


def sample(provider, scenario, seed):
    rng = random.Random(seed)
    size = 1000 if provider == 1 else 3000
    previous = parse(generar(Parametros(semilla=provider, skus=size)).encode())
    ranges = ESCENARIOS[scenario][1]
    parameters = {name: rng.uniform(*limits) for name, limits in ranges.items()}
    current = parse(generar(Parametros(semilla=seed, **parameters), previous.stock).encode())
    score = suspicion(previous.stock, current.stock)
    return {**score, "rows": current.lines, "sku": len(current.stock),
            "discarded": len(current.discarded), "parse_error_rate": current.error_rate}


def evaluate(seed=16, train_count=200, test_count=50):
    observations = []
    for provider in (1, 2):
        for index in range(train_count):
            values = sample(provider, "estable", seed * 1_000_003 + provider * 10_003 + index)
            assert values["p"] <= 0.5  # Simula el arranque con aceptaciones por reglas.
            observations.append({"run_id": len(observations) + 1, "provider_id": provider,
                                 "features": values, "accepted_at": datetime(2026, 1, 1, tzinfo=UTC)
                                 + timedelta(hours=index * 5)})
    payload = fit(observations, TrainingConfig())
    model = NormalityModel(payload)
    results = []
    for order, (scenario, (label, _)) in enumerate(ESCENARIOS.items()):
        rules = ml = 0
        for provider in (1, 2):
            for index in range(test_count):
                values = sample(provider, scenario,
                                seed * 10_000_019 + order * 100_003 + provider * 1009 + index)
                rules += values["p"] > 0.5
                ml += not model.classify(provider, values)["accepted"]
        results.append((scenario, label, test_count * 2, rules, ml))
    return payload, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=16)
    parser.add_argument("--train-per-provider", type=int, default=200)
    parser.add_argument("--test-per-scenario-provider", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]
                        / "docs/entregas/ML-NORMALIDAD-EVALUACION.md")
    args = parser.parse_args()
    if min(args.train_per_provider, args.test_per_scenario_provider) < 10:
        parser.error("Usar al menos diez ejemplos por grupo")
    payload, results = evaluate(args.seed, args.train_per_provider, args.test_per_scenario_provider)
    lines = [
        "# Evaluación sintética del detector global de normalidad", "",
        "Diseño vigente: [ADR-0016](../adr/0016-normalidad-global-y-aprendizaje-durable.md).",
        "Este ensayo no activa modelos ni usa feeds reales. Entrena sólo con escenarios estables",
        "que pasan las reglas; evalúa semillas disjuntas. Las etiquetas se usan exclusivamente",
        "para medir en prueba, nunca para entrenar. Los agotamientos y depuraciones legítimos",
        "son novedades deliberadas: no pertenecen a la normalidad observada en entrenamiento.", "",
        f"Semilla {args.seed}; dos proveedores sintéticos de 1.000 y 3.000 SKU; "
        f"{args.train_per_provider} aceptados por proveedor separados cinco horas.",
        f"Configuración: `{payload['config']}`. Versión `{payload['version']}`.",
        f"Bibliotecas: `{payload['libraries']}`. Hash del conjunto `{payload['dataset_hash']}`.", "",
        "| Escenario reservado | Etiqueta de evaluación | Ejemplos | Rechazo por reglas | Rechazo por ML |",
        "|---|---|---:|---:|---:|",
    ]
    for name, label, n, rules, ml in results:
        kind = "Defectuoso" if label else "Sano (falsa cuarentena si se rechaza)"
        lines.append(f"| {name} | {kind} | {n} | {rules / n:.1%} | {ml / n:.1%} |")
    lines += ["", "En defectuosos, rechazo equivale a detección; en sanos, a falsas cuarentenas.",
              "ML decide por sí mismo: la columna de reglas es una referencia, no una decisión combinada.",
              "El resultado depende de estos escenarios y no acredita precisión con proveedores reales.",
              "Las novedades legítimas rechazadas no se aprenderían automáticamente en producción:",
              "es una limitación del aprendizaje sólo de aceptados. Tampoco se puede detectar un",
              "defecto que conserve las siete estadísticas de entrada.", "",
              "Reproducir con `uv run --group ml python scripts/ml_evaluar_normalidad.py`.", ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Evaluación sintética guardada en {args.output}")


if __name__ == "__main__":
    main()
