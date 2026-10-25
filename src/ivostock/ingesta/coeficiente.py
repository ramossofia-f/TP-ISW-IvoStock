"""Guarda determinista de inventario (RF-13, ADR-0007)."""

from collections.abc import Mapping
from dataclasses import dataclass

TOLERANCIA_D = 0.10
TOLERANCIA_Z = 0.25
UMBRAL_CUARENTENA = 0.5


@dataclass(frozen=True)
class Senales:
    D: float
    Z: float

    @property
    def d(self) -> float:
        return min(1.0, self.D / TOLERANCIA_D)

    @property
    def z(self) -> float:
        return min(1.0, self.Z / TOLERANCIA_Z)

    @property
    def p(self) -> float:
        return 1 - (1 - self.d) * (1 - self.z)

    @property
    def sospechosa(self) -> bool:
        return self.p > UMBRAL_CUARENTENA


def calcular(previo: Mapping[str, int], nuevo: Mapping[str, int]) -> Senales:
    if not previo:
        return Senales(0.0, 0.0)
    ausentes = sum(1 for sku in previo if sku not in nuevo)
    con_stock = [sku for sku, valor in previo.items() if valor > 0]
    ceros_nuevos = sum(1 for sku in con_stock if nuevo.get(sku) == 0)
    return Senales(ausentes / len(previo), ceros_nuevos / len(con_stock) if con_stock else 0.0)
