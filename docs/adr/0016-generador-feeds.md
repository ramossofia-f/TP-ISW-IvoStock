---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0016 — Generador de feeds sintéticos reproducibles

## Context and Problem Statement

El feed real permite medir el caso habitual, pero no provocar truncados, errores de formato o cambios controlados. RF-37 identifica un generador como componente del entorno de demostración.

## Decision Drivers

* Ejercitar normalización, cuarentena y recuperación a demanda.
* Controlar volumen y deltas sin modificar la fuente real.

## Considered Options

* **Opción A** — Generador configurable con semilla y parámetros registrados.
* **Opción B** — Editar archivos reales manualmente para cada prueba.

## Decision Outcome

Chosen option: "Opción A — generador configurable", porque permite repetir escenarios y comparar resultados entre revisiones. Produce feeds con volumen, separador, encabezado, corrupción y deriva de stock configurables. Registra semilla y configuración junto al escenario; se ejecuta bajo demanda, sin requerir un servidor permanente.

Complementa las pruebas con Celesa real. Desde M5 aporta corrupciones sintéticas al protocolo del ADR-0003, manteniendo separados los modos usados para entrenar y evaluar.

### Consequences

* Good, porque los escenarios de falla y de carga son repetibles.
* Bad, porque los datos sintéticos pueden no representar las anomalías reales.

### Confirmation

* Repetir semilla y configuración, comprobar el mismo resultado y verificar que los casos inyectados activan las respuestas esperadas de ingesta.

## Pros and Cons of the Options

* **A:** controla entradas y fallas; requiere mantener el generador.
* **B:** permite preparar un caso rápido; dificulta reproducirlo y conocer sus cambios exactos.

## More Information

* [PRD](../prd/PRD.md): RF-21, RF-28 y RF-37; [roadmap](../roadmap/ROADMAP.md): P2 y M5.
* [ML](0003-componente-ml-deteccion-anomalias.md) e [ingesta](0006-worker-ingesta.md).
