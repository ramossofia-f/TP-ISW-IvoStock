---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0015 — Observabilidad por componente y verificación externa

## Context and Problem Statement

La sincronización cruza varios procesos y puede quedar pendiente durante horas. El tablero debe explicar su estado y los registros permitir recuperar fallas sin conservar un portal de historial completo.

## Decision Drivers

* Correlación por corrida, tarea y vínculo (RF-30, RNF-09).
* Salud por feed y tienda (RF-31, RF-33).
* Mediciones externas para RNF-01 y RNF-19.

## Considered Options

* **Opción A** — Logs estructurados, métricas y health checks por componente, más observador externo.
* **Opción B** — Solo logs locales y una pantalla de estado general.

## Decision Outcome

Chosen option: "Opción A — observabilidad por componente", porque permite seguir una operación y distinguir fallas externas, fallas propias y atraso. El tablero consume la copia de estado de la API, con su fecha; no consulta directamente al motor.

Los 429 de MercadoLibre quedan en diagnóstico técnico. No se exponen secretos ni se reincorpora el historial completo retirado. El observador externo conserva evidencia de latencia y disponibilidad según PRD §4. La herramienta de recolección y visualización queda pendiente.

### Consequences

* Good, porque estado operativo y medición de cumplimiento tienen evidencia identificable.
* Bad, porque hay que mantener correlación, retención y sondas.

### Confirmation

* Seguir una corrida entre procesos y contrastar las métricas con el simulador. Ejecutar las sondas de 24 horas y reportar cada conjunto por separado.

## Pros and Cons of the Options

* **A:** permite diagnóstico y verificación independiente; agrega instrumentación.
* **B:** reduce trabajo inicial; no explica fallas parciales ni acredita los objetivos externos.

## More Information

* [PRD](../prd/PRD.md): §4, §5, RF-24, RF-30 a RF-33 y RNF-09.
* [Roadmap](../roadmap/ROADMAP.md): M6 y M8; monitoreo del modelo en [ADR-0003](0003-componente-ml-deteccion-anomalias.md).
