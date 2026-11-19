"""Variables de una corrida contra el último inventario aceptado (ADR-0015).

Una sola función para entrenamiento e inferencia: si cambia una variable, cambia en ambos lados.
Ambos feeds son `Feed` de `ivostock.ingesta.normalizacion`; su `stock` conserva el orden del
archivo, que `cola` necesita. En la ingesta, el previo se obtiene del snapshot de la última
corrida aceptada, no de la tabla `stock`, que no guarda el orden.
"""

from ivostock.ingesta.coeficiente import calcular
from ivostock.ingesta.normalizacion import Feed

NOMBRES = ("D", "Z", "errores", "variacion", "cola", "cambios", "ks")


def _ks(previo: list[int], nuevo: list[int]) -> float:
    """Estadístico de Kolmogorov-Smirnov entre dos muestras de cantidades (0 si alguna es vacía)."""
    if not previo or not nuevo:
        return 0.0
    a, b = sorted(previo), sorted(nuevo)
    i = j = 0
    maximo = 0.0
    while i < len(a) and j < len(b):
        valor = min(a[i], b[j])
        while i < len(a) and a[i] == valor:
            i += 1
        while j < len(b) and b[j] == valor:
            j += 1
        maximo = max(maximo, abs(i / len(a) - j / len(b)))
    return maximo


def calcular_variables(previo: Feed, nuevo: Feed) -> dict[str, float]:
    """Variables en el orden de `NOMBRES`. Sin inventario previo todas valen cero."""
    if not previo.stock:
        return dict.fromkeys(NOMBRES, 0.0)
    senales = calcular(previo.stock, nuevo.stock)
    orden = list(previo.stock)
    ausentes = [sku for sku in orden if sku not in nuevo.stock]
    # Un truncamiento corta la cola del archivo: los ausentes ocupan las últimas posiciones.
    # Con bajas dispersas, en cambio, casi ninguno cae ahí.
    cola = len(set(ausentes) & set(orden[-len(ausentes):])) / len(ausentes) if ausentes else 0.0
    comunes = [sku for sku in orden if sku in nuevo.stock]
    cambios = sum(previo.stock[sku] != nuevo.stock[sku] for sku in comunes)
    return {
        "D": senales.D,
        "Z": senales.Z,
        "errores": nuevo.error_rate,
        "variacion": (len(nuevo.stock) - len(orden)) / len(orden),
        "cola": cola,
        "cambios": cambios / len(comunes) if comunes else 0.0,
        "ks": _ks(list(previo.stock.values()), list(nuevo.stock.values())),
    }
