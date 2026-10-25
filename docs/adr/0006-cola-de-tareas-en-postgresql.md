# ADR-0006: Cola de tareas de actualización durable en PostgreSQL

## Contexto y problema

La cola de tareas entre el comparador y el worker de publicación es el mecanismo de integración del motor. El patrón declarado del sistema es de servicios con cola de eventos, y esta cola es la pieza que tiene que resistir fallas. Hay que decidir dónde vive.

Los requisitos que tiene que cumplir son exigentes y específicos:

* **Prioridad con envejecimiento (RF-23):** las tareas salen según la prioridad de su proveedor, pero una tarea de prioridad baja no puede esperar indefinidamente.
* **A lo sumo una tarea pendiente por vínculo (RF-46):** una tarea nueva **reemplaza** a la pendiente del mismo vínculo, conservando su posición de prioridad. Eso acota la cola de una tienda a su cantidad de vínculos activos (RNF-06b).
* **Cero trabajo perdido (RNF-06):** ante 10 cierres abruptos, incluida la caída del servicio de cola, con tareas pendientes y en curso. Incluye las órdenes de stock cero de RF-47, que no se pueden reconstruir a partir del stock del proveedor.
* **Entrega al menos una vez** con efectos idempotentes (RNF-04), **dead letter** para errores no reintentables (RF-27) y estado operativo por vínculo consistente con la cola (RF-30).
* **Caudal bajo:** la cuota es de 60 llamadas por minuto por tienda. Con 2 tiendas, la cola entrega como mucho unas 2 tareas por segundo.

## Factores de decisión

* Cumplir RF-46 de forma natural, sin un mecanismo de deduplicación aparte.
* Durabilidad ante la caída de cualquier proceso, incluido el almacén de la cola.
* Una sola fuente de verdad para tareas, estado operativo y dead letters, actualizada en la misma transacción.
* No sumar servicios que el equipo tenga que operar sin necesidad, en un plazo de semanas.

## Opciones consideradas

* **Opción A**: Redis, con un conjunto ordenado por tienda y la cola reconstruible desde PostgreSQL ante una pérdida.
* **Opción B**: Tabla de tareas en la base PostgreSQL del motor, tomadas con `SELECT ... FOR UPDATE SKIP LOCKED`.
* **Opción C**: RabbitMQ con colas de prioridad.
* **Opción D**: Redis Streams con grupos de consumidores.
* **Opción E**: Redis decide el orden de las tareas y PostgreSQL conserva el trabajo y las intenciones de corte.

## Decisión

Opción elegida: "Opción B: cola durable en PostgreSQL", porque es la única en la que RF-46 y RNF-06 salen directo de las garantías de la base, en lugar de construirse encima.

* **Reemplazo por vínculo (RF-46):** un índice único sobre las tareas pendientes de cada vínculo. Encolar es un `INSERT ... ON CONFLICT DO UPDATE` que cambia el valor deseado y conserva la fecha original de encolado, y por lo tanto la posición.
* **Prioridad con envejecimiento (RF-23):** el worker toma la siguiente tarea ordenando por una prioridad efectiva que combina la prioridad del proveedor y el tiempo de espera. La fórmula se especifica en el SRD.
* **Tareas en curso:** una tarea tomada queda marcada con un vencimiento. Si el worker muere, la tarea vuelve a estar disponible al vencer, y el reintento es idempotente (RNF-04).
* **Versiones por vínculo:** cada tarea lleva una versión que crece con cada reemplazo. El worker confirma el stock solo si la versión que escribió sigue siendo la vigente, de modo que la confirmación de un intento viejo no borra una tarea nueva pendiente. Las escrituras de un mismo vínculo no se ejecutan en paralelo, para que un reintento viejo no pise un valor nuevo.
* **Durabilidad (RNF-06):** las tareas, las órdenes de stock cero, el estado operativo y las dead letters se escriben en la misma base y en la misma transacción. La caída del almacén de la cola es la caída de PostgreSQL, que conserva lo confirmado por su registro de escritura anticipada.
* **Aviso al comparador (RF-45):** la ingesta registra la corrida aceptada en la misma transacción que actualiza el estado vigente, y el comparador la toma de esa tabla. Para no consultar en un bucle, la base avisa con `LISTEN/NOTIFY`, y la tabla sigue siendo la fuente de verdad si el aviso se pierde.

### Consecuencias

* A favor, porque RF-46 es una restricción de la base y no un algoritmo: no hay forma de que queden dos tareas pendientes para el mismo vínculo.
* A favor, porque no hay dos fuentes de verdad que reconciliar después de una caída: tarea, estado operativo y dead letter cambian juntos o no cambian.
* A favor, porque las órdenes de stock cero de RF-47 quedan persistidas como cualquier otra tarea.
* A favor, porque no suma ningún servicio: la base del motor ya existe (ADR-0005).
* En contra, porque una cola en una base relacional no escala como un broker dedicado. Con el caudal máximo de unas 2 tareas por segundo que impone la cuota externa, esto no es un límite. Se registra como cuello de botella identificado hacia los 10⁸ vínculos del sistema original (RNF-13).
* En contra, porque la cola agrega carga a la base del motor. Se mitiga con índices sobre las columnas de selección y con la cota de RNF-06b.

### Confirmación

* P3 verifica con tests que N notificaciones sobre el mismo vínculo dejan una sola tarea pendiente con el último valor (RNF-04, RF-46), y que la cola de una tienda nunca supera sus vínculos activos (RNF-06b).
* La campaña de RNF-06 de P3 corta el worker con una tarea en curso y corta PostgreSQL con trabajo pendiente, y comprueba cero trabajo perdido.
* Las cuatro condiciones de resolución de R-01 de P3 se miden con esta cola.

## Ventajas y desventajas de las opciones

### Opción A: Redis con conjunto ordenado, reconstruible

* A favor, porque es rápido y el conjunto ordenado resuelve la prioridad.
* A favor, porque el reemplazo por vínculo es simple con una clave por vínculo.
* En contra, porque la durabilidad depende de la configuración de persistencia, y puede perder el último segundo ante una caída.
* En contra, porque la reconstrucción solo recupera diferencias de inventario: las órdenes de stock cero de RF-47 hay que persistirlas igual en PostgreSQL, y quedan dos fuentes de verdad.
* En contra, porque tarea y estado operativo viven en almacenes distintos y pueden quedar inconsistentes entre sí.

### Opción B: Cola durable en PostgreSQL

* A favor, porque RF-46, RNF-06 y RF-30 salen de las garantías transaccionales de la base.
* A favor, porque no agrega servicios.
* En contra, porque su techo de caudal es menor que el de un broker, aunque muy superior a lo que permite la cuota externa.

### Opción C: RabbitMQ con colas de prioridad

* A favor, porque es un broker durable diseñado para esto, con entrega al menos una vez.
* En contra, porque no permite reemplazar un mensaje ya encolado: RF-46 exige un registro externo de la última versión por vínculo y descartar los mensajes vencidos al consumirlos.
* En contra, porque la prioridad se fija al publicar el mensaje: el envejecimiento de RF-23 obliga a volver a publicar.
* En contra, porque suma un servicio a operar, y el estado operativo sigue en PostgreSQL.

### Opción D: Redis Streams con grupos de consumidores

* A favor, porque da entrega al menos una vez y seguimiento de mensajes en curso.
* En contra, porque un stream es un registro que solo crece: no tiene prioridad ni reemplazo por vínculo.
* En contra, porque comparte las limitaciones de durabilidad de la opción A.

### Opción E: Redis para ordenar, PostgreSQL para conservar

* A favor, porque perder Redis no pierde trabajo: PostgreSQL guarda tareas, versiones e intenciones de corte, y la cola se reconstruye desde ahí.
* A favor, porque Redis resuelve el orden por prioridad con estructuras propias.
* En contra, porque hay dos lugares con el estado de la cola que hay que reconciliar después de cada caída, y el reemplazo por vínculo tiene que mantenerse igual en los dos.
* En contra, porque PostgreSQL ya resuelve el orden con una consulta ordenada, con el caudal que permite la cuota. Se puede reconsiderar si las mediciones del POC muestran que la selección de tareas en PostgreSQL es un cuello de botella.

## Más información

* Responde al insumo que dejó abierto ADR-0002: las diferencias son reconstruibles, pero las órdenes de corte no, y por eso la cola se persiste.
* Relacionado con RF-23, RF-27, RF-30, RF-45, RF-46, RF-47, RNF-03, RNF-04, RNF-06, RNF-06b, RNF-13 y R-01.
* Redis sigue en el sistema solo para el control de cuota (ADR-0005).
