# ADR-0008: Arquitectura de servicios separados por responsabilidad, integrados por una cola de tareas

## Contexto y problema

La consigna exige un patrón arquitectónico definido y justificado, y evalúa la coherencia entre ese patrón y lo construido. Hay que decidir cómo se reparte el sistema en procesos.

El trabajo tiene ritmos muy distintos. La ingesta descarga y normaliza unas 255.000 filas cada 30 minutos. El comparador reacciona a corridas nuevas y también a cambios de vínculos que no dependen de ningún feed. La publicación espera durante horas a que la cuota de 60 llamadas por minuto por tienda le permita escribir. El catálogo de una tienda nueva se lee en segundo plano, y la API atiende consultas interactivas que no pueden quedar trabadas detrás de nada de lo anterior (RNF-20, RNF-21).

## Factores de decisión

* Que una tienda lenta o caída no frene la ingesta ni las demás tiendas (RNF-05).
* Que el comparador atienda todos sus disparadores con la misma regla: corridas aceptadas, alta de vínculo, encendido y apagado, baja de proveedor, desconexión de tienda y tienda que sale de *degradada* (RF-43, RF-45, RF-47).
* Que la espera por la cuota externa no ocupe a ningún componente con otra responsabilidad (S-08, RF-24).
* Que la API y el motor sean independientes (RNF-20).
* Que la cantidad de piezas sea abordable para tres personas en el plazo de la cursada.

## Opciones consideradas

* **Opción A**: Monolito: un solo proceso que descarga, compara, publica y atiende la API.
* **Opción B**: Monolito modular: un solo proceso con módulos internos bien separados.
* **Opción C**: Servicios separados por responsabilidad (API core, ingesta, comparador, publicación, catálogo y simulador), integrados por la base del motor y una cola de tareas durable.
* **Opción D**: Microservicios con una base de datos propia por servicio.

## Decisión

Opción elegida: "Opción C: servicios separados por responsabilidad, integrados por una cola", porque cada servicio tiene un ritmo y un modo de falla propios, y la cola de tareas entre el comparador y la publicación es lo que permite que cada uno avance a su ritmo sin perder trabajo. Es el patrón de **servicios con cola de eventos** que declara el PRD.

| Servicio | Responsabilidad | Qué no hace |
|---|---|---|
| **API core** | Autenticación, configuración, solicitudes del usuario y consulta de su copia del estado (desde M1) | No llama al motor ni lee su base (ADR-0007) |
| **Ingesta** | Descarga, snapshot crudo, normalización, validación y cuarentena de cada corrida. Su único producto es el estado vigente | No conoce vínculos ni escribe en tiendas |
| **Comparador** | Compara el estado vigente con el último stock confirmado de cada vínculo afectado y encola solo las diferencias | No llama a MercadoLibre |
| **Publicación** | Toma tareas por prioridad y escribe contra la interfaz de marketplace, con cuota, reintentos, idempotencia y dead letters | No calcula diferencias |
| **Catálogo** | Lectura inicial en dos etapas, webhooks y validación de IDs cargados a mano | Comparte la cuota con la publicación (RF-48) |
| **Simulador** | Implementa el contrato de MercadoLibre para desarrollo y demostración (ADR-0001) | No forma parte del motor |

La ingesta y el comparador quedan separados a propósito: los acopla solo el estado vigente, y el comparador tiene disparadores que no son feeds. Los servicios del motor comparten su base PostgreSQL, que es donde viven el estado vigente y la cola (ADR-0006). No se parte esa base por servicio, porque las garantías de la cola salen de que tarea, estado operativo y dead letter cambian en la misma transacción.

### Consecuencias

* A favor, porque una tienda caída, una corrida en cuarentena o una lectura de catálogo larga quedan acotadas a su servicio.
* A favor, porque cada servicio se puede reiniciar por separado, que es lo que ejercita la campaña de cierres abruptos de RNF-06.
* A favor, porque el patrón declarado se ve en el código: un proceso por servicio en `docker-compose` y la cola como única vía entre comparador y publicación.
* En contra, porque hay más procesos para levantar, monitorear y probar que en un monolito.
* En contra, porque las tareas en curso y los avisos entre servicios tienen que recuperarse después de una caída. Lo resuelve la cola durable de ADR-0006.
* Neutral, porque los servicios del motor comparten base. Es una decisión deliberada, y la separación de bases se exige solo entre la API y el motor.

### Confirmación

* `docker-compose` levanta un contenedor por servicio (ADR-0009).
* Un test corta la publicación mientras la ingesta procesa una corrida, y verifica que la corrida termina y que la tarea se publica al volver el servicio.
* El SRD de la Entrega 2 incluye el diagrama con estos servicios y la cola entre comparador y publicación.

## Ventajas y desventajas de las opciones

### Opción A: Monolito

* A favor, porque es lo más simple de construir y desplegar.
* En contra, porque la espera por la cuota y una tienda lenta frenan todo el proceso, incluida la ingesta.
* En contra, porque la API comparte proceso con el motor, en contra de RNF-20.

### Opción B: Monolito modular

* A favor, porque ordena el código por responsabilidad sin sumar procesos.
* En contra, porque una caída o un bloqueo de un módulo detiene a los demás, y no permite reiniciar servicios por separado.
* En contra, porque sigue sin cumplir la independencia entre la API y el motor de RNF-20.

### Opción C: Servicios separados con cola

* A favor, porque aísla ritmos y fallas, y hace visible el patrón declarado.
* En contra, porque suma procesos y exige recuperar trabajo en curso.

### Opción D: Microservicios con base propia por servicio

* A favor, porque es el máximo aislamiento entre servicios.
* En contra, porque partir la base del motor rompe la transacción que da las garantías de la cola, y obliga a sincronizar datos entre servicios.
* En contra, porque la cantidad de piezas excede lo que tres personas pueden construir y operar en el plazo.

## Más información

* Relacionado con PRD §2.3, RF-12, RF-20 a RF-30, RF-43, RF-45 a RF-48, RNF-05, RNF-06, RNF-20 y R-01.
* Integra las propuestas de componentes que redactó Francisco Ortega (API core y workers de ingesta, comparación, publicación y catálogo).
