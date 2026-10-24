---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0014 — Pipeline de CI/CD versionado

## Context and Problem Statement

El proyecto tiene varios componentes y caminos de falla comprometidos. El roadmap exige CI desde P0 e imágenes y despliegue efímero en M7.

## Decision Drivers

* Build y tests desde la Entrega 2 (RNF-12).
* Detectar credenciales versionadas (RNF-07).
* Imágenes reproducibles y configuración por entorno (RNF-11).

## Considered Options

* **Opción A** — Pipeline automático definido en el repositorio.
* **Opción B** — Compilar, probar y desplegar manualmente.

## Decision Outcome

Chosen option: "Opción A — pipeline versionado", porque aplica los mismos controles a las contribuciones del equipo. Ejecuta build, tests y chequeo de secretos; incluye progresivamente los contract tests y escenarios de falla conforme se implementan.

En M7 construye y publica imágenes identificadas por revisión y habilita el despliegue efímero con configuración externa. La elección del proveedor de CI, registro y hosting queda pendiente; no se exige un servicio permanentemente encendido.

### Consequences

* Good, porque cada revisión queda asociada a resultados verificables.
* Bad, porque el pipeline y sus entornos requieren mantenimiento y tiempo de ejecución.

### Confirmation

* Provocar un fallo de test y un secreto ficticio detectable para verificar el rechazo; comprobar que la imagen desplegada corresponde a la revisión validada.

## Pros and Cons of the Options

* **A:** repite controles sin depender de la memoria del equipo; requiere configurar el runner.
* **B:** reduce preparación inicial; permite omitir controles y dificulta reproducir la entrega.

## More Information

* [PRD](../prd/PRD.md): RNF-07, RNF-11 y RNF-12.
* [Roadmap](../roadmap/ROADMAP.md): P0 y M7; [entorno local](0013-docker-compose.md).
