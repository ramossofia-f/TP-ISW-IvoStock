---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0004 — Frontend web para configuración y operación

## Context and Problem Statement

El usuario necesita configurar integraciones, aprobar vínculos y revisar fallas sin programar. El componente frontend está identificado en el documento de validación y en CLAUDE.md.

## Decision Drivers

* Operación desde el navegador, con sesión autenticada (RF-01).
* Consulta disponible con el motor detenido (RNF-20).

## Considered Options

* **Opción A** — Aplicación web de formularios y tablas.
* **Opción B** — Herramienta de línea de comandos como interfaz definitiva.

## Decision Outcome

Chosen option: "Opción A — aplicación web", porque permite configurar y operar el sistema sin conocimientos técnicos. Consume únicamente la API core y muestra la fecha del último estado y las operaciones pendientes. Ante un 429 propio conserva la pantalla y muestra el tiempo de `Retry-After` (RNF-22).

El framework queda pendiente; este ADR justifica el componente, sin cerrar esa elección.

### Consequences

* Good, porque concentra configuración, vínculos y salud operativa en una interfaz accesible.
* Bad, porque requiere mantener pantallas y gestionar estados asíncronos.

### Confirmation

* Verificar configuración, consulta con el motor detenido y conservación de pantalla ante un 429 propio.

## Pros and Cons of the Options

* **A:** facilita la operación cotidiana; agrega desarrollo de interfaz.
* **B:** reduce trabajo inicial; exige conocimientos técnicos. Se admite como recorte del POC, según el roadmap.

## More Information

* [PRD](../prd/PRD.md): RF-15, RF-17, RF-31, RNF-20 y RNF-22.
* [Separación de servidores](0018-api-y-motor-en-servidores-separados.md).
