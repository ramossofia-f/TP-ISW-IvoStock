# Evaluación del detector de corridas defectuosas

Generado por `scripts/ml_entrenar.py` ([ADR-0015](../adr/0015-detector-de-feeds-anomalos.md)). Los escenarios y sus etiquetas son sintéticos: estas cifras no acreditan el comportamiento con un proveedor real.

En corridas defectuosas, la proporción en cuarentena es el recall; en normales, la tasa de falsas cuarentenas. «Guarda + modelo» es la decisión combinada: el modelo sólo agrega cuarentenas.

## Inventarios sintéticos

Modelo `195c1c6cfe4e`, semilla 15, 300 ejemplos por escenario y conjunto, umbral 0,0296. El conjunto de prueba es disjunto del de entrenamiento y del de validación, donde se fija el umbral.

| Escenario | Tipo | Guarda | Guarda + modelo |
|---|---|---|---|
| `estable` | normal | 0,0% | 0,3% |
| `agotamiento_masivo` | normal | 93,7% | 93,7% |
| `depuracion` | normal | 58,3% | 58,3% |
| `truncado_leve` | defectuosa | 15,3% | 100,0% |
| `truncado` | defectuosa | 100,0% | 100,0% |
| `ceros_masivos` | defectuosa | 100,0% | 100,0% |
| `corrupto` | defectuosa | 100,0% | 100,0% |
| **Todas las defectuosas** | | 78,8% | 100,0% |
| **Todas las normales** | | 50,7% | 50,8% |

## Escenarios sobre el inventario real

Los mismos escenarios aplicados sobre el inventario preparado de Celesa (255129 SKU, SHA-256 `fb68d3ef33a8`), 30 ejemplos por escenario. El archivo queda fuera de Git; se versiona sólo este resumen. Los SKU y las cantidades son reales; el orden del archivo lo fija el generador (por SKU) y las alteraciones son sintéticas.

| Escenario | Tipo | Guarda | Guarda + modelo |
|---|---|---|---|
| `estable` | normal | 0,0% | 0,0% |
| `agotamiento_masivo` | normal | 100,0% | 100,0% |
| `depuracion` | normal | 43,3% | 46,7% |
| `truncado_leve` | defectuosa | 23,3% | 100,0% |
| `truncado` | defectuosa | 100,0% | 100,0% |
| `ceros_masivos` | defectuosa | 100,0% | 100,0% |
| `corrupto` | defectuosa | 100,0% | 100,0% |
| **Todas las defectuosas** | | 80,8% | 100,0% |
| **Todas las normales** | | 47,8% | 48,9% |

## Coeficientes

Sobre variables estandarizadas: a mayor valor absoluto, más peso.

| Variable | Coeficiente |
|---|---|
| `D` | +2,242 |
| `Z` | +1,878 |
| `errores` | +6,281 |
| `variacion` | -2,242 |
| `cola` | +5,960 |
| `cambios` | +0,556 |
| `ks` | +2,323 |
