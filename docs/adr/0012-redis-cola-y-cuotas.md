---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0012 — Redis para planificación y cuotas, con trabajo durable en PostgreSQL

## Context and Problem Statement

Los documentos proponen Redis para prioridad y cuota por tienda. RNF-06 exige recuperar también tareas en curso y órdenes de stock cero, que no se reconstruyen solo desde el feed.

## Decision Drivers

* Prioridad con envejecimiento y reemplazo por vínculo (RF-23, RF-46).
* Cuota compartida de lecturas y escrituras (RF-48).
* Cero trabajo vigente perdido en la campaña de RNF-06.

## Considered Options

* **Opción A** — Redis como único registro de tareas.
* **Opción B** — Cola y cuotas únicamente en PostgreSQL.
* **Opción C** — Redis para planificar; PostgreSQL conserva trabajo e intención.

## Decision Outcome

Chosen option: "Opción C — Redis con registro durable en PostgreSQL", porque permite reconstruir la cola sin perder trabajo aceptado.

Antes de encolar, el motor persiste tarea, versión, prioridad e intención de corte. Redis mantiene la planificación; PostgreSQL distingue trabajo pendiente, en curso y terminal. Reemplazar conserva la antigüedad; confirmar una versión vieja no elimina la nueva pendiente.

Publicador y catálogo comparten control atómico por tienda, con reparto 40/20 y préstamo hasta 60. Si Redis cae, se conservan tareas y se suspenden llamadas; al recuperar contadores se espera una ventana completa de cuota. Persistencia y réplica complementan el registro durable.

El intercambio usa otro Redis (ADR-0018); la cuota propia usa recursos de la API.

### Consequences

* Good, porque perder la planificación no elimina tareas ni órdenes de corte.
* Bad, porque hay que reconciliar PostgreSQL y Redis y operar más de un almacén.

### Confirmation

* Ejecutar los 10 cierres de RNF-06, incluida caída de Redis; comprobar órdenes cero, versiones concurrentes, cota de cola, envejecimiento y cuota después de recuperar.

## Pros and Cons of the Options

* **A:** concentra la cola; necesita demostrar durabilidad sin otra fuente de recuperación.
* **B:** reduce almacenes; concentra planificación y cuotas en la base transaccional.
* **C:** recupera desde el registro; agrega reconciliación. Se revisará con mediciones del POC.

## More Information

* [PRD](../prd/PRD.md): RF-46, RF-47, RNF-06 y RNF-06b.
* [Deltas](0002-propagacion-por-deltas.md), [PostgreSQL](0010-postgresql.md) y [separación](0018-api-y-motor-en-servidores-separados.md).
