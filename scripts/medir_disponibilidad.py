"""Fija una ventana de RNF-07 y exporta su evidencia, incluyendo cortes y faltantes.

El muestreo lo realiza metrics; este comando no necesita quedar abierto durante 24 horas.
Ejecutar dentro del servicio cli, que monta data/ de forma persistente.
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ivostock import metrics
from ivostock.db import database
from ivostock.health import WORKERS


def save_new(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, ensure_ascii=False, default=str)
        output.write("\n")


def start(engine, path, revision, machine, note="", now=None):
    if not revision or not machine:
        raise ValueError("Indicar --revision y --machine para identificar la campaña")
    state = metrics.current(engine)
    if state["age_seconds"] is None or not 0 <= state["age_seconds"] < 120:
        raise ValueError("La muestra de métricas no está vigente; preparar el stack antes de medir")
    components = {**state["state"]["components"], **state["workers"]}
    required = ("api", "simulator", "provider", *WORKERS)
    if not all(components.get(name, {}).get("available") is True for name in required):
        raise ValueError("API, proveedor, simulador y los cuatro workers deben estar disponibles")
    begin = metrics.minute(now or datetime.now(UTC)) + timedelta(minutes=1)
    campaign = {
        "start": begin.isoformat(),
        "end": (begin + timedelta(hours=24)).isoformat(),
        "expected_samples": 1440,
        "revision": revision,
        "machine": machine,
        "note": note,
    }
    save_new(path, campaign)
    return campaign


def report(engine, path, now=None):
    campaign = json.loads(path.read_text(encoding="utf-8"))
    begin, end = (datetime.fromisoformat(campaign[key]) for key in ("start", "end"))
    if any(at.tzinfo is None or at.second or at.microsecond for at in (begin, end)):
        raise ValueError("La ventana guardada requiere minutos completos con zona horaria")
    if end - begin != timedelta(hours=24) or campaign["expected_samples"] != 1440:
        raise ValueError("La campaña debe conservar 24 horas y 1.440 posiciones")
    captured = now or datetime.now(UTC)
    if captured < end:
        raise ValueError(f"La ventana todavía no terminó: {campaign['end']}")
    summary = metrics.summary(engine, begin, end)
    evidence = {
        "campaign": campaign,
        "captured_at": captured.isoformat(),
        "summary": summary,
        "history": metrics.history(engine, begin, end),
        "meets_rnf07": all(
            summary["availability"][name]["availability_percent"] >= 99
            for name in ("api", "engine")
        ),
    }
    destination = path.with_name(path.stem + "-resultado.json")
    save_new(destination, evidence)
    return {
        "evidence": str(destination),
        "summary": summary,
        "meets_rnf07": evidence["meets_rnf07"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "report"))
    parser.add_argument("--campaign", type=Path, default=Path("data/evidencia/rnf07-campana.json"))
    parser.add_argument("--revision")
    parser.add_argument("--machine")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    try:
        if args.command == "start":
            result = start(database(), args.campaign, args.revision, args.machine, args.note)
        else:
            result = report(database(), args.campaign)
    except FileExistsError:
        parser.exit(1, "El archivo ya existe: conservar la ventana y su evidencia original.\n")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
