---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0007 — Worker comparador con disparadores independientes

## Context and Problem Statement

El ADR-0002 define cómo calcular los deltas. Falta justificar el componente que ejecuta esa comparación: debe responder tanto a nuevas corridas como a cambios de vínculos y configuración.

## Decision Drivers

* Procesar todos los disparadores con la misma regla (RF-43, RF-45).
* Conservar el último trabajo vigente por vínculo (RF-46, RNF-06).

## Considered Options

* **Opción A** — Comparador separado, activado por notificaciones durables.
* **Opción B** — Comparación embebida únicamente en la ingesta.

## Decision Outcome

Chosen option: "Opción A — comparador separado", porque altas de vínculos, ON/OFF, bajas y recuperaciones de tiendas requieren comparar sin descargar otro feed.

Lee el estado vigente y el último stock confirmado en la base del motor. Persiste únicamente las diferencias como trabajo por vínculo, reemplazando la tarea pendiente sin perder su posición de prioridad. Las órdenes de corte conservan explícitamente la intención de stock cero; una notificación duplicada no duplica trabajo.

### Consequences

* Good, porque todos los disparadores usan la estrategia de deltas ya aceptada.
* Bad, porque requiere coordinar versiones y cambios concurrentes del vínculo.

### Confirmation

* Ejercitar cada disparador, duplicar notificaciones y verificar la cota de RNF-06b y la recuperación de órdenes de corte.

## Pros and Cons of the Options

* **A:** compara sin nuevas ingestas; agrega un proceso y coordinación durable.
* **B:** simplifica el recorrido del feed; deja sin resolver los disparadores ajenos a las corridas.

## More Information

* [Deltas](0002-propagacion-por-deltas.md), [ingesta](0006-worker-ingesta.md) y [cola](0012-redis-cola-y-cuotas.md).
* [PRD](../prd/PRD.md): RF-43, RF-45 a RF-47 y RNF-04.
