# ADR-0007: Intercambio entre la API y el motor por replicación lógica de PostgreSQL

## Contexto y problema

RNF-20 exige que la API de consulta y el motor tengan **bases de datos y CPU separados**, sin llamadas directas entre ambos. Con la interfaz y su API detenidas, el motor sigue sincronizando las integraciones ya configuradas. Con el motor detenido, la interfaz consulta su copia del último estado, con su fecha, y acepta solicitudes que quedan pendientes hasta que el motor vuelve (PRD §2.3). Hay que decidir cómo viajan la configuración y las solicitudes hacia el motor, y el estado operativo hacia la API.

La copia de consulta de la API también tiene que soportar RNF-21: 1.000 usuarios a una consulta por segundo, con p95 menor a 2 segundos, sin cargar la base del motor.

Esta decisión se implementa en M1, cuando se construyen la interfaz y su API. El POC se opera por línea de comandos directamente sobre el motor.

## Factores de decisión

* Bases separadas y ninguna llamada directa entre los procesos (RNF-20).
* Intercambio asíncrono y durable: nada se pierde si uno de los dos lados está detenido.
* Solicitudes idempotentes: una solicitud reenviada no genera trabajo duplicado.
* La menor cantidad de código e infraestructura nueva que cumpla lo anterior, en el plazo del MVP.

## Opciones consideradas

* **Opción A**: La API llama al motor por HTTP.
* **Opción B**: Una base compartida entre la API y el motor.
* **Opción C**: Un broker de mensajes (RabbitMQ) entre ambos, con tablas de salida en cada base para publicar de forma confiable.
* **Opción D**: Replicación lógica de PostgreSQL en los dos sentidos, sobre tablas dedicadas al intercambio.

## Decisión

Opción elegida: "Opción D: replicación lógica de PostgreSQL", porque da intercambio asíncrono y durable entre dos bases separadas con un mecanismo nativo del motor que ya usamos, sin un servicio adicional ni código de publicación y consumo de mensajes.

* **De la API al motor:** la API escribe la configuración y las solicitudes del usuario en tablas propias, cada solicitud con un identificador único. La base del motor se suscribe a esas tablas. El motor procesa cada solicitud una sola vez gracias a ese identificador.
* **Del motor a la API:** el motor publica tablas de consulta con el estado operativo por vínculo, las fallas, las corridas y el resultado de cada solicitud, con su fecha de actualización. La base de la API se suscribe y las consultas de la interfaz leen solo esa copia.
* **Si un lado está detenido,** el otro sigue trabajando con lo que tiene. Al volver, la suscripción recupera lo que se acumuló mientras tanto.
* **Las tablas de intercambio son un contrato:** son distintas de las tablas internas de cada lado, para que un cambio interno no rompa al otro.

### Consecuencias

* A favor, porque cumple RNF-20 sin ningún servicio nuevo: la replicación es parte de PostgreSQL.
* A favor, porque es durable por construcción: lo replicado es lo que cada base confirmó.
* A favor, porque la carga de consultas de RNF-21 cae solo sobre la base de la API, que puede tener sus propios recursos.
* En contra, porque los cambios de esquema de las tablas de intercambio hay que aplicarlos en los dos lados, en orden. Se mitiga manteniendo esas tablas pocas y estables, y versionando las migraciones juntas.
* En contra, porque si un suscriptor queda detenido mucho tiempo, la base que publica retiene registro de cambios. Se acota con un límite de retención configurado y se monitorea en M6.
* En contra, porque el patrón es menos explícito que un mensaje con nombre propio: el contrato son tablas, no eventos. Se documenta en el SRD.

### Confirmación

* M1 cierra con la prueba de independencia de RNF-20 en los dos sentidos (PRD §4), verificando que la consulta no depende de la base del motor.
* M8 incluye la prueba de RNF-21 sobre la copia de consulta, con el motor activo.

## Ventajas y desventajas de las opciones

### Opción A: Llamada HTTP de la API al motor

* A favor, porque es lo más simple de implementar.
* En contra, porque es una llamada directa, prohibida por RNF-20: con el motor detenido, la API no puede aceptar solicitudes ni mostrar el estado.

### Opción B: Base compartida

* A favor, porque no hay nada que sincronizar.
* En contra, porque RNF-20 exige bases separadas: la carga de consultas de RNF-21 competiría con el motor, y detener la base afectaría a los dos lados.

### Opción C: Broker de mensajes con tablas de salida

* A favor, porque es el patrón de eventos más explícito: cada mensaje tiene nombre y forma propios.
* A favor, porque un broker como RabbitMQ es durable y entrega al menos una vez.
* En contra, porque suma un servicio a operar.
* En contra, porque publicar de forma confiable exige una tabla de salida y un proceso que la lea en cada lado, más los consumidores y la deduplicación: es el código que la replicación lógica ya resuelve.

### Opción D: Replicación lógica de PostgreSQL

* A favor, porque es nativa, durable y no suma servicios.
* A favor, porque cada lado conserva su base y su CPU.
* En contra, porque acopla los dos lados a través del esquema de las tablas de intercambio, y exige cuidar su evolución.

## Más información

* Relacionado con PRD §2.3, RNF-19, RNF-20, RNF-21 y RF-41.
* Las bases y el resto de los almacenes se justifican en ADR-0005.
