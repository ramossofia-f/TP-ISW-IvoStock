---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0006 — Worker de ingesta independiente

## Context and Problem Statement

Las fuentes entregan inventarios completos con formatos y calidad variables. Descargar y normalizar aproximadamente 255.000 SKU no debe ocupar una petición de usuario ni depender de las tiendas.

## Decision Drivers

* Reejecución, snapshot crudo y validación de corridas (RF-20 a RF-22).
* Una corrida en cuarentena no modifica el estado vigente ni propaga deltas (RF-28).

## Considered Options

* **Opción A** — Worker de ingesta separado del comparador.
* **Opción B** — Descargar, comparar y publicar dentro del mismo proceso.

## Decision Outcome

Chosen option: "Opción A — worker de ingesta separado", porque el proveedor se procesa una vez y su estado sirve a todas las tiendas. Conserva el snapshot, normaliza y valida; publica una versión completa del estado vigente únicamente al aceptar la corrida. La actualización y su notificación durable se coordinan en la base del motor.

No consulta vínculos ni escribe stock en tiendas. La señal de anomalías usa el baseline y, desde M5, el modelo con fallback del ADR-0003.

### Consequences

* Good, porque una tienda lenta no bloquea la ingesta ni obliga a repetirla.
* Bad, porque hay que coordinar versiones de corrida y recuperación entre procesos.

### Confirmation

* Verificar normalización, cuarentena y reejecución; interrumpir después de persistir el estado y comprobar que la comparación se recupera. Medir RNF-02 incluyendo el cálculo de deltas.

## Pros and Cons of the Options

* **A:** separa fallas y reutiliza la ingesta; exige notificaciones durables.
* **B:** simplifica el arranque; acopla fuentes, vínculos y cuota externa.

## More Information

* [PRD](../prd/PRD.md): RF-20 a RF-22, RF-28 y RNF-02.
* [Deltas](0002-propagacion-por-deltas.md), [ML](0003-componente-ml-deteccion-anomalias.md) y [snapshots](0011-object-storage-s3-minio.md).
