# Evaluación sintética del detector global de normalidad

Diseño vigente: [ADR-0016](../adr/0016-normalidad-global-y-aprendizaje-durable.md).
Este ensayo no activa modelos ni usa feeds reales. Entrena sólo con escenarios estables
que pasan las reglas; evalúa semillas disjuntas. Las etiquetas se usan exclusivamente
para medir en prueba, nunca para entrenar. Los agotamientos y depuraciones legítimos
son novedades deliberadas: no pertenecen a la normalidad observada en entrenamiento.

Semilla 16; dos proveedores sintéticos de 1.000 y 3.000 SKU; 200 aceptados por proveedor separados cinco horas.
Configuración: `{'min_runs': 10, 'history_per_provider': 200, 'half_life_days': 7.0, 'nu': 0.05}`. Versión `b8d0067730d4a6369ac9a8eecc663c51cdafe98325dd6cbca7feae3fa289d70a`.
Bibliotecas: `{'sklearn': '1.9.1', 'numpy': '2.5.4'}`. Hash del conjunto `e40c6edb48624f1fa2bdfa13b32be47f24525ea10b6a189d046e0e711402490c`.

| Escenario reservado | Etiqueta de evaluación | Ejemplos | Rechazo por reglas | Rechazo por ML |
|---|---|---:|---:|---:|
| estable | Sano (falsa cuarentena si se rechaza) | 100 | 0.0% | 8.0% |
| agotamiento_masivo | Sano (falsa cuarentena si se rechaza) | 100 | 95.0% | 100.0% |
| depuracion | Sano (falsa cuarentena si se rechaza) | 100 | 55.0% | 100.0% |
| truncado_leve | Defectuoso | 100 | 19.0% | 81.0% |
| truncado | Defectuoso | 100 | 100.0% | 100.0% |
| ceros_masivos | Defectuoso | 100 | 100.0% | 100.0% |
| corrupto | Defectuoso | 100 | 100.0% | 100.0% |

En defectuosos, rechazo equivale a detección; en sanos, a falsas cuarentenas.
ML decide por sí mismo: la columna de reglas es una referencia, no una decisión combinada.
El resultado depende de estos escenarios y no acredita precisión con proveedores reales.
Las novedades legítimas rechazadas no se aprenderían automáticamente en producción:
es una limitación del aprendizaje sólo de aceptados. Tampoco se puede detectar un
defecto que conserve las siete estadísticas de entrada.

Reproducir con `uv run --group ml python scripts/ml_evaluar_normalidad.py`.
