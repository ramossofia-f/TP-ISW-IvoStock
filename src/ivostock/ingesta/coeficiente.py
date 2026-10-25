"""Coeficiente de sospecha de CU-07. Es un score, no una probabilidad calibrada.

D: SKU del estado previo que no vienen en la corrida, sobre el total del estado previo.
Z: SKU presentes en la corrida con stock 0 que antes tenían stock > 0, sobre los que tenían
   stock > 0. Los ausentes no cuentan en Z: ya los mide D.

Las tolerancias son fijas y no se calibran: son los valores que saturan cada señal.
"""

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
    D = ausentes / len(previo)
    Z = ceros_nuevos / len(con_stock) if con_stock else 0.0
    return Senales(D, Z)
