---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0008 — Worker de publicación con cuota por tienda

## Context and Problem Statement

El comparador puede generar trabajo más rápido de lo que MercadoLibre permite escribir. Publicar dentro de la ingesta o de la API trasladaría esa espera a componentes con otras responsabilidades.

## Decision Drivers

* Límite asumido de 60 llamadas/minuto por tienda, compartido con catálogo (S-08, RF-48).
* Prioridad con envejecimiento, reintentos e idempotencia (RF-23 a RF-27).

## Considered Options

* **Opción A** — Worker que consume trabajo persistido por tienda.
* **Opción B** — Escrituras inmediatas desde el comparador o la API core.

## Decision Outcome

Chosen option: "Opción A — worker de publicación", porque desacopla el cálculo del caudal externo. Usa la interfaz de marketplace del ADR-0001 y el control de cuota compartido con catálogo: 40 llamadas habituales y 20 masivas, con préstamo hasta 60.

Conserva tareas en curso y serializa las escrituras de un vínculo para impedir que un reintento viejo sobrescriba un valor nuevo. Confirma el stock solo tras el éxito; los errores permanentes conservan contexto en dead letter. Un 429 externo espera y reintenta internamente, sin alerta ni fallo persistente.

### Consequences

* Good, porque las esperas y fallas de una tienda quedan acotadas a su trabajo.
* Bad, porque requiere recuperación de tareas en curso y coordinación por vínculo.

### Confirmation

* Verificar reparto 40/20, préstamo, envejecimiento y RNF-06, incluida la caída después de escribir y antes de confirmar.

## Pros and Cons of the Options

* **A:** controla cuota y recuperación; agrega coordinación de tareas.
* **B:** reduce componentes; bloquea al productor y dificulta reanudar escrituras.

## More Information

* [Marketplace](0001-marketplace-simulado-detras-de-interfaz.md), [catálogo](0009-worker-catalogo.md) y [cola](0012-redis-cola-y-cuotas.md).
* [PRD](../prd/PRD.md): RF-23 a RF-30 y RF-48.
