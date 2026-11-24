"""Conjunto etiquetado de corridas sintéticas para el detector (ADR-0015).

Cada ejemplo es un par (inventario previo, corrida nueva) generado con `ivostock.generador.feeds`
y una semilla derivada de la del conjunto: la misma semilla produce las mismas filas. Las etiquetas
son supuestos declarados, no observaciones de un proveedor real:

- Normales (0): deriva con agotamientos y bajas dispersas, incluidos agotamientos masivos de
  temporada y depuraciones de catálogo que la guarda frena.
- Defectuosas (1): truncamientos (también menores al 5 %, que la guarda acepta), ceros masivos
  y filas corruptas.
"""

import random
from dataclasses import dataclass

from ivostock.generador.feeds import Parametros, generar
from ivostock.ingesta.coeficiente import Senales
from ivostock.ingesta.normalizacion import normalizar
from ivostock.ml.variables import calcular_variables

SKUS = (300, 1500)

# Nombre, etiqueta y rangos uniformes de cada parámetro del generador.
ESCENARIOS = {
    "estable": (0, {"deriva": (0, 0.4), "ceros": (0, 0.03), "bajas": (0, 0.02)}),
    "agotamiento_masivo": (0, {"deriva": (0, 0.3), "ceros": (0.1, 0.3), "bajas": (0, 0.02)}),
    "depuracion": (0, {"deriva": (0, 0.3), "ceros": (0, 0.03), "bajas": (0.02, 0.08)}),
    "truncado_leve": (
        1,
        {"deriva": (0, 0.4), "ceros": (0, 0.03), "truncar": (0.005, 0.05), "bajas": (0, 0.01)},
    ),
    "truncado": (
        1,
        {"deriva": (0, 0.4), "ceros": (0, 0.03), "truncar": (0.05, 0.4), "bajas": (0, 0.01)},
    ),
    "ceros_masivos": (1, {"deriva": (0, 0.3), "ceros": (0.4, 1.0), "bajas": (0, 0.01)}),
    "corrupto": (1, {"deriva": (0, 0.3), "corruptas": (0.05, 0.5), "bajas": (0, 0.01)}),
}


@dataclass(frozen=True)
class Ejemplo:
    escenario: str
    etiqueta: int
    variables: dict[str, float]
    guarda: bool


def ejemplo(escenario: str, semilla: int, base: dict[str, int] | None = None) -> Ejemplo:
    """Con `base` (un inventario real), el previo es esa base y no un inventario sintético."""
    etiqueta, rangos = ESCENARIOS[escenario]
    azar = random.Random(semilla)
    skus = azar.randint(*SKUS)
    parametros = {nombre: azar.uniform(*rango) for nombre, rango in rangos.items()}
    previo = normalizar(generar(Parametros(semilla=semilla, skus=skus), base).encode())
    nuevo = normalizar(
        generar(Parametros(semilla=semilla + 1, skus=skus, **parametros), previo.stock).encode()
    )
    variables = calcular_variables(previo, nuevo)
    return Ejemplo(
        escenario, etiqueta, variables, Senales(variables["D"], variables["Z"]).sospechosa
    )


def conjunto(semilla: int, por_escenario: int, base=None) -> list[Ejemplo]:
    """`por_escenario` ejemplos de cada escenario; semillas separadas por escenario e índice."""
    return [
        ejemplo(escenario, semilla * 1_000_003 + orden * 100_003 + 2 * indice, base)
        for orden, escenario in enumerate(ESCENARIOS)
        for indice in range(por_escenario)
    ]
