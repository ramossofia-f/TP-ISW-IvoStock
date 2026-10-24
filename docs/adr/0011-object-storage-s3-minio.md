---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0011 — Snapshots inmutables en object storage S3 / MinIO

## Context and Problem Statement

Cada corrida debe conservar su entrada original para reproducir la ingesta, revisar cuarentenas y preparar datos de ML. Validación y CLAUDE.md proponen almacenamiento compatible con S3, con MinIO en local.

## Decision Drivers

* Snapshot crudo e inmutable por corrida (RF-20).
* Reproducción local y componentes sin estado local (RNF-10, RNF-11).
* Histórico para el dataset de ML del ADR-0003.

## Considered Options

* **Opción A** — Object storage compatible con S3; MinIO local.
* **Opción B** — Archivos crudos dentro de PostgreSQL.
* **Opción C** — Archivos en el disco del worker o en Git.

## Decision Outcome

Chosen option: "Opción A — object storage S3 / MinIO", porque separa los archivos históricos del estado transaccional y permite recuperarlos desde cualquier ejecución del worker.

Cada corrida guarda un objeto nuevo sin sobrescribir anteriores. PostgreSQL registra su referencia, checksum y metadatos de parseo; una corrida no se confirma sin snapshot completo. Credenciales y permisos impiden modificar objetos ya confirmados. Los datos permanecen fuera de Git.

### Consequences

* Good, porque se conserva la evidencia original para reprocesar y entrenar.
* Bad, porque hay que coordinar objetos y metadatos, y gestionar volumen y respaldo.

### Confirmation

* Recuperar un snapshot y comprobar su checksum; reprocesarlo y verificar que un reintento no sobrescribe el original.

## Pros and Cons of the Options

* **A:** separa archivos y transacciones; agrega un servicio.
* **B:** concentra la persistencia; mezcla el crecimiento histórico con la carga operativa.
* **C:** simplifica el prototipo; ata datos al proceso o hace crecer el repositorio.

## More Information

* [PRD](../prd/PRD.md): RF-20, RF-28 y RF-51; roadmap P2 y M5.
* [PostgreSQL](0010-postgresql.md) y [ML](0003-componente-ml-deteccion-anomalias.md).
