---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0009 — Worker de catálogo en background

## Context and Problem Statement

Conectar una tienda requiere leer su catálogo y mantenerlo mediante webhooks y validaciones manuales. Son operaciones externas largas que no deben mantener abierta una petición de usuario.

## Decision Drivers

* Lectura inicial en dos etapas y aviso de carga incompleta (RF-12).
* Cuota compartida entre lectura y publicación (RF-48).

## Considered Options

* **Opción A** — Worker de catálogo separado del publicador.
* **Opción B** — Leer el catálogo sincrónicamente desde la API core.

## Decision Outcome

Chosen option: "Opción A — worker de catálogo", porque permite reanudar lecturas y recibir nuevas publicaciones sin bloquear la interfaz. Primero recupera identificadores MLX y después stock y atributos; persiste avance y resultados en la base del motor.

Las notificaciones de webhooks y las solicitudes manuales quedan persistidas antes de procesarse. Las consultas al marketplace usan la interfaz única y el mismo control de cuota que el publicador, imputadas a su clase según el PRD. La API muestra el avance desde su copia de consulta.

### Consequences

* Good, porque las cargas incompletas se pueden identificar y reanudar.
* Bad, porque las lecturas compiten con escrituras y deben planificarse.

### Confirmation

* Interrumpir ambas etapas, repetir un webhook y comprobar recuperación sin duplicar publicaciones; verificar cuota compartida y reparto 40/20.

## Pros and Cons of the Options

* **A:** aísla la carga del catálogo; requiere persistir progreso.
* **B:** evita otro proceso; acopla la respuesta al volumen y disponibilidad externa.

## More Information

* [PRD](../prd/PRD.md): RF-11 a RF-14 y RF-48; roadmap P4 y M3.
* [Publicación](0008-worker-publicacion.md) y [separación](0018-api-y-motor-en-servidores-separados.md).
