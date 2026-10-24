---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0010 — PostgreSQL para estado y trabajo durable

## Context and Problem Statement

El sistema relaciona usuarios, proveedores, tiendas y vínculos, y debe conservar estado operativo y trabajo aceptado. PostgreSQL está propuesto en validación, CLAUDE.md y el roadmap.

## Decision Drivers

* Un único vínculo activo por publicación (INV-1).
* Transacciones y recuperación del trabajo (RNF-04, RNF-06).
* Bases y CPU independientes para API y motor (RNF-20).

## Considered Options

* **Opción A** — PostgreSQL con una instancia por conjunto.
* **Opción B** — Una base PostgreSQL compartida.
* **Opción C** — Archivos locales o Redis como único estado persistente.

## Decision Outcome

Chosen option: "Opción A — PostgreSQL independiente por conjunto", porque permite coordinar cambios de estado y trabajo en transacciones sin compartir el almacén entre API y motor.

La API conserva usuarios, solicitudes, configuración deseada y proyecciones consultables. El motor conserva configuración aplicada, catálogo, estado vigente, vínculos y trabajo operativo; valida INV-1 en su transacción. Cada base mantiene sus mensajes de salida y recibidos, según ADR-0018. Las credenciales se almacenan cifradas. Los snapshots crudos se guardan aparte.

### Consequences

* Good, porque datos de dominio y recuperación tienen un registro durable.
* Bad, porque mantener dos bases y sus proyecciones agrega operación y consistencia eventual.

### Confirmation

* Verificar INV-1 concurrentemente, caídas durante transacciones y consultas con la base del motor detenida. Medir RNF-21 con recursos declarados.

## Pros and Cons of the Options

* **A:** permite transacciones y aislamiento; exige operar dos instancias.
* **B:** simplifica consultas; incumple la independencia de RNF-20.
* **C:** simplifica casos pequeños; exige construir coordinación y restricciones adicionales.

## More Information

* [PRD](../prd/PRD.md): RF-03, RF-30, RF-39 y RNF-06.
* [Snapshots](0011-object-storage-s3-minio.md), [cola](0012-redis-cola-y-cuotas.md) y [separación](0018-api-y-motor-en-servidores-separados.md).
