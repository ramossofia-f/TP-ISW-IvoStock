---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0005 — API core como entrada de las operaciones de usuario

## Context and Problem Statement

La interfaz necesita autenticar usuarios, consultar estado y solicitar cambios de proveedores, tiendas y vínculos. Estas responsabilidades están agrupadas como API core en los documentos técnicos.

## Decision Drivers

* Autenticación y protección de credenciales (RF-01, RF-03, RNF-08).
* Reutilizar las operaciones desde la vía programática (RF-41).

## Considered Options

* **Opción A** — API core común para interfaz y clientes programáticos.
* **Opción B** — Acceso del frontend a bases y endpoints de cada worker.

## Decision Outcome

Chosen option: "Opción A — API core común", porque centraliza autenticación, validación y cuotas. Consulta su base propia y persiste cada solicitud con identidad estable antes de confirmarla como recibida; el motor informa después su ejecución o rechazo. Los reintentos no duplican operaciones.

La cuota de RNF-22 se comparte entre sesiones y clientes del usuario. No se agregan roles. El lenguaje y framework quedan pendientes de un ADR específico.

### Consequences

* Good, porque interfaz y clientes aplican las mismas reglas de acceso y admisión.
* Bad, porque una operación recibida puede seguir pendiente de ejecución y debe mostrarse así.

### Confirmation

* Verificar acceso sin sesión, cuota entre sesiones y solicitudes persistidas con el motor detenido. Medir RNF-21 con el motor activo.

## Pros and Cons of the Options

* **A:** ofrece un contrato común; requiere mantener la copia de consulta.
* **B:** evita una capa inicial; dispersa seguridad y acopla la interfaz al motor.

## More Information

* [PRD](../prd/PRD.md): §2.3, RNF-08 y RNF-20 a RNF-22; OpenAPI según RNF-16 cuando se incorpore RF-41.
* [Separación de servidores](0018-api-y-motor-en-servidores-separados.md).
