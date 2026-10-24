---
status: Propuesto
date: 2026-10-21
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0018 — API del frontend y motor en servidores separados

## Context and Problem Statement

La API atiende consultas interactivas; el motor procesa feeds y espera la cuota externa. Compartir CPU o base expone la consulta a la carga y los reinicios del motor. RNF-20 exige independencia en ambos sentidos.

## Decision Drivers

* Sincronizar con la API detenida; consultar y aceptar solicitudes con el motor detenido (RNF-20).
* Conservar trabajo aceptado (RNF-06) y verificar RNF-19 y RNF-21 por separado y bajo carga.

## Considered Options

* **Opción A** — API y motor en un servidor y una base compartidos.
* **Opción B** — Servidores separados con base compartida o llamadas síncronas entre ambos.
* **Opción C** — Servidores y bases independientes, comunicados por mensajes durables.

## Decision Outcome

Chosen option: "Opción C — servidores y bases independientes", porque aísla carga y reinicios y permite operar con el otro conjunto detenido.

Se proponen dos servidores o máquinas virtuales con CPU asignada por separado:

* **Servidor API:** frontend, API core y PostgreSQL propio: usuarios, configuración deseada, solicitudes y copia consultable del estado con su fecha.
* **Servidor motor:** workers y PostgreSQL propio: configuración aplicada, credenciales cifradas, catálogo, estado vigente, vínculos, tareas e intenciones de corte. Valida las invariantes y decide la ejecución.

Ninguno accede a la base del otro ni lo invoca directamente.

Se propone **outbox/inbox sobre un Redis de intercambio separado**. Cada emisor persiste cambio y mensaje en una transacción local y reenvía hasta que el destinatario confirma recepción durable. El consumidor registra identificador y efecto en su transacción: duplicados no repiten efectos y versiones por entidad descartan mensajes antiguos. La confirmación del transporte no basta para eliminar la salida.

La API confirma recepción tras persistir y muestra la solicitud pendiente hasta recibir ejecución o rechazo. Los resultados actualizan su copia local. Si el transporte cae, se conservan mensajes para reenvío; consultas e integraciones ya configuradas continúan con datos locales.

### Consequences

* Good, porque consultas y sincronización toleran reinicios del otro conjunto.
* Bad, porque duplica datos y exige deduplicación, confirmaciones y control del atraso.
* Neutral, porque separar no aumenta la cuota externa ni acredita rendimiento.

### Confirmation

* Probar ambos sentidos de RNF-20, incluida la caída de la base del motor durante consultas.
* Interrumpir transporte y confirmaciones; comprobar recuperación, duplicados y versiones, incluidas órdenes cero.
* Documentar bases y CPU separadas; medir RNF-21 y RNF-19. Compose local no acredita dos servidores.

## Pros and Cons of the Options

* **A:** simplifica despliegue y transacciones; comparte carga y fallas e incumple RNF-20.
* **B:** separa procesos; conserva dependencias que impiden la autonomía exigida.
* **C:** aísla ejecución y datos; requiere sincronización asíncrona y más operación.

## More Information

* [PRD](../prd/PRD.md): §2.3 y §4; [roadmap](../roadmap/ROADMAP.md): P0, P5 y M8.
* [PostgreSQL](0010-postgresql.md), [Redis](0012-redis-cola-y-cuotas.md) y [Compose](0013-docker-compose.md).
* Contratos del intercambio al SRD; política masiva y perfil de deltas pendientes según el PRD.
