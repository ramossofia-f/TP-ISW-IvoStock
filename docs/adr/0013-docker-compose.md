---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0013 — Docker Compose para el entorno local

## Context and Problem Statement

La cátedra debe levantar API, frontend, workers, simulador y almacenes sin credenciales de terceros. El roadmap P0 y RNF-10 ya prevén Docker Compose.

## Decision Drivers

* Un procedimiento de arranque reproducible (RNF-10).
* Imágenes y configuración reutilizables por entorno (RNF-11).

## Considered Options

* **Opción A** — Docker Compose con servicios y volúmenes declarados.
* **Opción B** — Instalación manual de cada proceso y almacén.
* **Opción C** — Kubernetes como requisito del entorno local.

## Decision Outcome

Chosen option: "Opción A — Docker Compose", porque describe el entorno completo sin introducir un orquestador adicional. Declara configuración por entorno, health checks, reinicio de procesos y volúmenes persistentes para los almacenes. Los secretos se suministran fuera del repositorio.

API y motor conservan servicios, redes y bases diferenciados. El arranque local en una computadora permite desarrollar; la evidencia de servidores y CPU separados de RNF-20 se verifica con la topología del ADR-0018.

### Consequences

* Good, porque todos usan la misma definición del entorno y pueden provocar reinicios.
* Bad, porque un arranque local no demuestra por sí solo disponibilidad ni aislamiento de recursos.

### Confirmation

* Levantar desde un checkout limpio sin credenciales externas y reiniciar procesos conservando los volúmenes. Documentar el procedimiento en el README al implementarlo.

## Pros and Cons of the Options

* **A:** concentra el arranque en archivos versionados; exige mantenerlos.
* **B:** evita contenedores; aumenta diferencias y pasos manuales.
* **C:** ofrece más mecanismos de orquestación; excede la necesidad local del equipo.

## More Information

* [PRD](../prd/PRD.md): RNF-07 y RNF-10 a RNF-12; [roadmap](../roadmap/ROADMAP.md): P0.
* [Separación de servidores](0018-api-y-motor-en-servidores-separados.md).
