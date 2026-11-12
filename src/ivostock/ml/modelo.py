"""Inferencia del detector de corridas defectuosas en Python puro (ADR-0015).

`modelo.json` guarda medias, escalas, coeficientes e intercepto de una regresión logística
entrenada con `scripts/ml_entrenar.py`. Cargarlo no ejecuta código: es aritmética.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ivostock.ml.variables import NOMBRES

RUTA = Path(__file__).with_name("modelo.json")


@dataclass(frozen=True)
class Modelo:
    version: str
    medias: tuple[float, ...]
    escalas: tuple[float, ...]
    coeficientes: tuple[float, ...]
    intercepto: float
    umbral: float

    @classmethod
    def cargar(cls, ruta: Path = RUTA) -> "Modelo":
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if tuple(datos["variables"]) != NOMBRES:
            raise ValueError("El modelo fue entrenado con otras variables")
        return cls(
            datos["version"],
            tuple(datos["medias"]),
            tuple(datos["escalas"]),
            tuple(datos["coeficientes"]),
            datos["intercepto"],
            datos["umbral"],
        )

    def puntaje(self, variables: dict[str, float]) -> float:
        """Probabilidad estimada de que la corrida sea defectuosa."""
        z = self.intercepto + sum(
            c * (variables[nombre] - m) / s
            for nombre, m, s, c in zip(NOMBRES, self.medias, self.escalas, self.coeficientes)
        )
        # Forma estable de la sigmoide para |z| grande.
        if z >= 0:
            return 1 / (1 + math.exp(-z))
        e = math.exp(z)
        return e / (1 + e)


def cuarentena(guarda_sospechosa: bool, puntaje: float, umbral: float) -> str | None:
    """Motivo de cuarentena o None. El modelo sólo agrega: nunca libera lo que frena la guarda."""
    if guarda_sospechosa:
        return "guarda"
    if puntaje > umbral:
        return "ml"
    return None
