---
status: Aceptado
date: 2026-09-20
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0002 — Propagación por deltas contra el estado vigente, no reescritura de catálogo

## Context and Problem Statement

La fuente real (Celesa) entrega **inventario completo, no incrementos**: cada 30 minutos publica un archivo con ~650.000 pares `SKU;stock`, sin marca de "qué cambió desde la última vez". Del otro lado, el sistema mantiene del orden de 10⁵ vínculos publicación–SKU repartidos en K tiendas.

La pregunta es qué escribe el sistema en cada corrida. La cota que decide es dura y ajena al diseño propio: la API de MercadoLibre admite **60 req/min por tienda** (S-08), o sea 3.600 escrituras por hora y por tienda, y ese presupuesto es **compartido** entre escribir stock y leer catálogo (RF-48). Reescribir el catálogo completo de una tienda con 10⁵ publicaciones cuesta ~28 horas de cuota a caudal pleno, para una fuente que se actualiza 48 veces por día. Con ese esquema RNF-01 (p95 bajo 6 horas, p100 bajo 12) es inalcanzable por aritmética, no por implementación.

Como la fuente no informa el cambio, **el delta lo tiene que derivar el sistema**, y hay que decidir contra qué lo compara.

## Decision Drivers

* Cota dura de 60 req/min por tienda, compartida entre escritura y lectura (S-08, RF-48). Ninguna decisión de infraestructura propia la mueve.
* RNF-01: p95 en menos de 6 horas, p100 en menos de 12, sobre el 100 % de los vínculos activos.
* RNF-14: el trabajo contra la API debe ser proporcional a los **cambios**, no al catálogo; una corrida sin cambios produce **cero escrituras**.
* RNF-02: una corrida de 650.000 SKU procesada en menos de 10 minutos.
* RNF-03 y RNF-06: ningún cambio se pierde en silencio, ni siquiera ante caída del worker o del broker.
* Una escritura que falló tiene que poder recuperarse en la corrida siguiente, no desaparecer.
* Las fuentes reales no ofrecen un modo incremental: lo que no esté en el archivo, el sistema no lo puede pedir.

## Considered Options

* **Opción A** — Reescritura completa: cada corrida aceptada escribe el stock de todas las publicaciones vinculadas.
* **Opción B** — Delta entre snapshots: comparar la corrida N contra la corrida N−1 del proveedor y propagar las diferencias del feed.
* **Opción C** — Delta contra el estado vigente materializado: la ingesta reemplaza el estado vigente del proveedor (RF-22) y un comparador separado contrasta ese estado contra el **último valor confirmado de cada vínculo**, encolando solo las diferencias (RF-45).
* **Opción D** — Delta provisto por la fuente: pedirle al proveedor que informe solo lo que cambió.

## Decision Outcome

Chosen option: "Opción C — delta contra el estado vigente materializado", porque es la única que hace el trabajo proporcional a los cambios **y** conserva la capacidad de corregirse. La opción A no entra en el presupuesto de la API. La opción D no está en el contrato de las fuentes reales y no depende del equipo. La opción B sí entra en presupuesto, pero pierde los cambios que fallaron al escribirse: si una escritura muere en dead letter, la corrida siguiente no ve diferencia en el feed y el delta se evapora, dejando la publicación desfasada para siempre. La opción C no tiene ese agujero porque compara contra lo que la tienda tiene, no contra lo que el feed traía.

La decisión fija el pipeline en dos procesos separados y acoplados solo por el estado vigente: **snapshot crudo → normalización → estado vigente** (ingesta, RF-20 a RF-22) y **estado vigente → comparación contra vínculos → delta encolado** (comparador, RF-45). El comparador atiende además los disparadores que no son feeds: alta de vínculo, ON/OFF, baja de proveedor, desconexión de tienda, tienda que sale de degradada. El encolado es idempotente por vínculo (RF-46).

### Consequences

* Good, porque el consumo de la API pasa a ser proporcional a los cambios reales: una corrida sin cambios no gasta una sola llamada (RNF-14), y con eso RNF-01 pasa a ser alcanzable.
* Good, porque el delta es **reconstruible** en cualquier momento como `estado vigente − último valor confirmado`. Eso da la red de seguridad de RNF-06 (una tarea perdida se vuelve a derivar) y convierte la durabilidad de la cola en un problema de disponibilidad, no de pérdida de datos — matiz que se decide en su propio ADR.
* Good, porque una escritura fallida se reintenta sola en la corrida siguiente: la diferencia contra el valor confirmado sigue ahí hasta que se aplique.
* Good, porque al crear un vínculo se compara el stock del proveedor contra el que MercadoLibre reporta para esa publicación y se encolan **solo las diferencias**, en lugar de escribir el catálogo entero de arranque.
* Good, porque el reemplazo por vínculo de RF-46 acota la cola pendiente de una tienda a su cantidad de vínculos activos, sin importar cuántas corridas se acumulen.
* Bad, porque el sistema mantiene estado derivado (estado vigente + último valor confirmado por vínculo) que puede desincronizarse de la tienda. Si alguien escribe stock desde el frontend de MercadoLibre —cosa que el propio sistema pide hacer cuando una tienda queda degradada—, el valor confirmado miente y el sistema **no** escribe, dejando la publicación desfasada. Se mitiga con relectura de catálogo, que compite por la misma cuota.
* Bad, porque la decisión descansa en S-07 (el volumen de deltas por corrida es una fracción chica del total de vínculos). Si ese supuesto se rompe, el sistema degenera hacia el costo de la opción A y RNF-01 deja de cumplirse.
* Neutral, porque la comparación recorre **todos** los vínculos del proveedor en cada corrida, no solo los que cambiaron: es O(vínculos) contra la base propia, que es barato y no consume cuota, pero no es gratis y entra en el presupuesto de RNF-02.
* Neutral, porque la semántica de RF-22 (un SKU ausente vale cero) hace que un feed truncado se traduzca en una avalancha de deltas a cero. Esa es la razón por la que la validación de corrida y la cuarentena de CU-07 son requisito y no adorno.

### Confirmation

* Test de RNF-14: una corrida idéntica a la anterior produce **cero** llamadas a la API. Se mide llamadas por corrida contra cantidad de deltas, y la métrica queda expuesta en el tablero de salud.
* Test de RNF-02: corrida de 650.000 SKU (feed real de Celesa) procesada en menos de 10 minutos.
* Test de recuperación: matar el worker con tareas pendientes y verificar que la cola se reconstruye desde el estado vigente sin perder ningún delta (RNF-03, RNF-06).
* Test del camino de la opción B que se quiso evitar: una escritura que termina en dead letter debe volver a encolarse en la corrida siguiente aunque el feed no haya cambiado.

## Pros and Cons of the Options

### Opción A — Reescritura completa

* Good, porque es trivial de implementar y de razonar: no hay estado derivado que mantener ni que pueda desincronizarse.
* Good, porque es autocorrectiva por construcción: cualquier desvío se corrige en la corrida siguiente.
* Bad, porque no entra en el presupuesto de la API: 10⁵ publicaciones a 3.600 escrituras por hora son ~28 horas por tienda, contra una fuente que se actualiza cada 30 minutos.
* Bad, porque hace el trabajo proporcional al catálogo, que es exactamente lo que RNF-14 prohíbe.

### Opción B — Delta entre snapshots consecutivos del feed

* Good, porque el trabajo es proporcional a los cambios y se calcula sin tocar la base de vínculos.
* Good, porque es barato: alcanza con guardar el snapshot anterior.
* Bad, porque **pierde los cambios que fallaron**: si la escritura de un delta muere en dead letter, la comparación siguiente no ve diferencia en el feed y la publicación queda desfasada indefinidamente. Rompe RNF-03 en la práctica.
* Bad, porque no cubre los disparadores que no son feeds (alta de vínculo, ON/OFF, tienda que sale de degradada): habría que resolverlos por un camino aparte.
* Bad, porque no sirve para el alta de vínculo, donde lo que hay que comparar es contra lo que la tienda reporta, no contra una corrida anterior.

### Opción C — Delta contra el estado vigente materializado

* Good, porque el trabajo contra la API es proporcional a los cambios y la corrida sin cambios cuesta cero.
* Good, porque se autocorrige: el delta persiste hasta que la escritura se confirma.
* Good, porque un mismo comparador atiende todos los disparadores, sean feeds o no.
* Good, porque el delta es reconstruible, lo que da una red de seguridad barata ante pérdida de cola.
* Bad, porque introduce estado derivado que hay que mantener y que puede mentir si la tienda se modifica por fuera del sistema.
* Bad, porque obliga a recorrer todos los vínculos del proveedor en cada corrida.

### Opción D — Delta provisto por la fuente

* Good, porque sería el menor trabajo posible: el sistema solo propaga.
* Bad, porque ninguna de las fuentes relevadas lo ofrece; Celesa publica inventario completo.
* Bad, porque depende de que un tercero cambie su contrato, algo fuera del control del equipo y del plazo del TP.
* Bad, porque un delta perdido en tránsito sería irrecuperable sin un mecanismo de reconciliación, que es justamente la opción C.

## More Information

* Relacionado con PRD §3 (RF-20 a RF-23, RF-45, RF-46, RF-48), §4 (RNF-01, RNF-02, RNF-03, RNF-06, RNF-14), S-07, S-08, R-01.
* Esta decisión **no** resuelve dónde vive la cola de deltas: que la cola sea reconstruible es un insumo de ese ADR (cola en Redis reconstruible vs. cola durable en PostgreSQL), no su conclusión.
* Tampoco fija el algoritmo de comparación (diff completo en memoria vs. comparación incremental en base); eso se decide con datos de RNF-02 durante el POC.
* La opción A sobrevive como **reconciliación periódica** de baja prioridad, si el desfase por escrituras externas resulta medible. No es la vía de propagación.
