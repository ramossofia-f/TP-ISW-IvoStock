---
status: Aceptado
date: 2026-09-19
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0001 — Marketplace simulado detrás de una interfaz única

## Context and Problem Statement

El sistema escribe stock en publicaciones de MercadoLibre. Hay que decidir contra qué escribe durante el desarrollo, el POC, el MVP y la corrección.

Tres restricciones chocan entre sí. Escribir sobre publicaciones productivas tiene consecuencias comerciales reales para la empresa que motiva el proyecto. El sistema debe poder levantarse y corregirse localmente sin credenciales externas (RNF-10), y la cátedra corrige levantando el sistema, exista o no un deploy vivo. Y el PRD compromete demostrar caminos de falla —cuota agotada, token revocado a mitad de corrida, publicación cerrada, tienda caída, feed corrupto (criterios de éxito 5 y 6)— que una API productiva no permite provocar a demanda.

## Decision Drivers

* Nunca escribir stock contra publicaciones productivas reales.
* El sistema completo debe levantarse localmente con un procedimiento simple, sin credenciales de terceros (RNF-10).
* Sin costos significativos ni servicios siempre encendidos.
* Los caminos de falla tienen que poder provocarse a demanda, en un video de 5 a 12 minutos.
* El límite de consumo real (60 req/min por tienda, S-08) ordena todo el diseño: si el entorno de prueba no lo aplica, el POC no ejercita el caso que importa.
* Conectar una tienda productiva más adelante debe ser un cambio de configuración, no una reescritura del motor.

## Considered Options

* **Opción 1** — API real sobre una cuenta productiva de la empresa.
* **Opción 2** — API real sobre una cuenta de prueba de MercadoLibre.
* **Opción 3** — Stubs o mocks simples en los tests, sin servicio corriendo.
* **Opción 4** — Simulador propio que implementa el contrato, detrás de una interfaz de marketplace con dos implementaciones (simulada y real) seleccionables por configuración.

## Decision Outcome

Chosen option: "Opción 4 — simulador propio detrás de una interfaz única", porque es la única que satisface las tres restricciones a la vez: cero riesgo comercial, reproducible localmente por un tercero sin credenciales, y capaz de provocar los caminos de falla que el PRD se compromete a demostrar. Las opciones 1 y 2 fallan el criterio de reproducibilidad y el de provocar fallas; la 3 falla el de validar el motor, que es justamente lo que el TP evalúa.

Los workers escriben **siempre** contra la interfaz de marketplace (RF-38). El simulador reproduce el contrato real: OAuth 2.0 completo (authorization code, refresh, revocación), catálogo, escritura de stock, webhooks, límite de consumo de 60 req/min por tienda **con respuesta 429 al superarlo**, la **semántica de stock 0** (escribir `available_quantity = 0` pausa la publicación con subestado `out_of_stock`, y escribir un valor mayor a 0 la reactiva) y errores reintentables y no reintentables. El catálogo sintético toma sus SKU del feed real de Celesa (RF-35, RF-36), de modo que el matching se ejercite contra datos verdaderos de un lado.

### Consequences

* Good, porque el sistema se levanta y se corrige entero en local, con `docker-compose`, sin credenciales de nadie.
* Good, porque cuota agotada, token revocado a mitad de corrida y publicación cerrada se provocan por configuración, y cada uno puede tener su test.
* Good, porque todo el conocimiento del contrato vive detrás de la interfaz: un cambio de la API de MercadoLibre se paga en un solo componente.
* Good, porque conectar una tienda real es seleccionar la otra implementación, sin tocar el motor de sincronización.
* Bad, porque construir el simulador es trabajo que no es el problema del TP, y compite por el tiempo del equipo.
* Bad, porque la integración real queda validada **por contrato, no por uso en producción** (limitación declarada, R-04). Si el simulador difiere de la API real, el sistema falla recién contra la API real.
* Good, porque reproducir la semántica de stock 0 es lo que hace demostrable el ciclo apagar→reponer de RF-47: sin ella el POC no distinguiría una publicación pausada por falta de stock —que está sana y se reactiva sola— de una publicación muerta (RF-32), que es un problema distinto y se atiende distinto.
* Neutral, porque el simulador no mide por sí mismo los objetivos de latencia de RNF-01: eso lo hace un observador externo al sistema, que registra el drenado de la cola. El sistema no se califica a sí mismo, y al simulador solo se le exige aplicar la cuota con fidelidad.

### Confirmation

* **Contract tests que corren contra ambas implementaciones.** Es el mecanismo que acota el riesgo de divergencia: lo que pasa contra el simulador debe pasar contra la API real.
* Punto de control de fin de P1 del roadmap: si el simulador no reproduce la semántica de cuota, no se avanza.
* El README identifica explícitamente qué está simulado, y el video lo declara en lugar de disimularlo.
* Revisión del simulador contra la documentación pública de MercadoLibre: OAuth 2.0, endpoints de catálogo y de stock, webhooks, límites de consumo y taxonomía de errores.

## Pros and Cons of the Options

### Opción 1 — API real sobre una cuenta productiva

* Good, porque es fidelidad máxima: es el sistema real.
* Bad, porque una escritura equivocada de stock tiene consecuencias comerciales inmediatas sobre una empresa real.
* Bad, porque no es reproducible: la cátedra no puede correr el sistema sin credenciales privadas de la empresa.
* Bad, porque no permite provocar cuota agotada, token revocado ni publicación cerrada cuando hace falta.

### Opción 2 — API real sobre una cuenta de prueba

* Good, porque mantiene fidelidad alta sin riesgo comercial.
* Neutral, porque puede sumarse más adelante como validación complementaria del contrato, sin cambiar esta decisión.
* Bad, porque requiere credenciales propias del grupo: sin ellas el sistema no se corrige.
* Bad, porque sigue sin permitir provocar fallas a demanda.
* Bad, porque la viabilidad de los usuarios de prueba de MercadoLibre para este caso de uso no fue verificada por el equipo.

### Opción 3 — Stubs o mocks simples

* Good, porque es lo más barato de construir y mantener.
* Bad, porque no implementa el contrato (OAuth, cuota, webhooks, taxonomía de errores), así que no valida el motor: los caminos de falla que el TP evalúa quedarían sin ejercitar.
* Bad, porque un mock vive dentro del test: no hay un sistema levantable de punta a punta para corregir ni para demostrar.

### Opción 4 — Simulador que implementa el contrato + interfaz con dos implementaciones

* Good, porque es reproducible localmente y sin costo.
* Good, porque provoca fallas a demanda y aplica el mismo límite de 60 req/min que la API real.
* Good, porque la interfaz deja la puerta abierta a la tienda productiva.
* Bad, porque hay que construirlo y mantenerlo sincronizado con el contrato real.
* Bad, porque la divergencia contra la API real es un riesgo que se acota con contract tests, pero no se elimina.

## More Information

* Relacionado con PRD §7, R-04, S-06, RF-35, RF-36, RF-38, RNF-10, S-08.
* El simulador y los generadores son **requisitos funcionales del sistema**, no herramientas de testing: se evalúan como parte del producto.
* Depende del alcance acotado al pilar de sincronización de stock (PRD §0 y documento de validación): es lo que hace abordable construir el simulador.
