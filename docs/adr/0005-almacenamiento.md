# ADR-0005: PostgreSQL, almacenamiento de objetos y Redis, cada uno para una necesidad distinta

## Contexto y problema

El sistema guarda tres tipos de datos con necesidades muy distintas, y hay que decidir dónde vive cada uno.

1. **Datos de configuración y operación:** proveedores, tiendas, vínculos, estado vigente por proveedor (SKU y stock), estado operativo por vínculo (RF-30), tareas pendientes y dead letters (RF-27). Son datos relacionados entre sí, que se modifican en transacciones y que tienen invariantes que no pueden romperse. Por ejemplo, INV-1: una publicación tiene un único vínculo activo (RF-39).
2. **Snapshots crudos de cada corrida (RF-20):** el archivo tal como llegó, inmutable, para reproducir corridas, revisar cuarentenas y armar el dataset de ML (M5). El feed de Celesa pesa unos 4 MB y llega cada 30 minutos: unos 190 MB por día y unos 5,8 GB por mes, solo para un proveedor.
3. **Control de cuota por tienda:** el límite de 60 llamadas por minuto (RF-24, RF-48), con el reparto 40/20 y el préstamo del cupo ocioso. Lo consultan varios procesos a la vez, antes de cada llamada a MercadoLibre, incluidas las lecturas de catálogo.

La consigna pide combinar motores de almacenamiento solo cuando cada uno responda a una necesidad real del sistema. La devolución de la Entrega 1 observó que el roadmap usaba PostgreSQL, Redis y almacenamiento de objetos sin justificarlos.

## Factores de decisión

* Integridad transaccional y restricciones declarativas para los datos de operación (INV-1, RF-46).
* Snapshots inmutables, baratos de guardar en volumen y fuera de la base transaccional.
* Control de cuota atómico y compartido entre procesos, sin que todos compitan por la misma fila de una base.
* Levantamiento local con `docker-compose` y sin costo (RNF-10), con equivalentes gestionados en capa gratuita para la readiness cloud (RNF-11).
* Componentes sin estado local (RNF-11): nada importante puede quedar en el disco de un contenedor.

## Opciones consideradas

* **Opción A**: Solo PostgreSQL, con los snapshots como binarios en la base y la cuota en una tabla.
* **Opción B**: PostgreSQL para los datos de operación, almacenamiento de objetos compatible con S3 (MinIO en local) para los snapshots y Redis para el control de cuota.
* **Opción C**: PostgreSQL y Redis, con los snapshots en el sistema de archivos local.
* **Opción D**: MongoDB para todo.

## Decisión

Opción elegida: "Opción B: PostgreSQL, almacenamiento de objetos y Redis", porque cada motor resuelve una de las tres necesidades y ninguno se usa para algo que otro ya resuelve.

* **PostgreSQL** guarda configuración, estado vigente, vínculos, estado operativo, tareas y dead letters. Las invariantes se expresan como restricciones: INV-1 es un índice único parcial sobre las publicaciones con vínculo activo, y el reemplazo de RF-46 es un índice único sobre las tareas pendientes de cada vínculo (ADR-0006). Hay dos bases separadas, una para el motor y otra para la API de consulta, por RNF-20 (ADR-0007).
* **El almacenamiento de objetos** guarda cada snapshot con una clave que identifica proveedor y corrida, y nunca se sobrescribe. PostgreSQL guarda solo la referencia y el hash del contenido.
* **Redis** guarda los contadores de cuota por tienda y por clase de trabajo, con operaciones atómicas y vencimiento automático. No guarda trabajo: si Redis se cae y pierde sus contadores, se recupera con contadores vacíos, y el peor caso es una ráfaga que MercadoLibre responde con 429, que el motor ya maneja con espera y reintento (RF-24). Ninguna tarea depende de Redis para no perderse.

### Consecuencias

* A favor, porque las invariantes viven en la base y no solo en el código: un segundo vínculo activo sobre la misma publicación es rechazado por PostgreSQL aunque el código tenga un error.
* A favor, porque los snapshots no inflan la base transaccional ni sus copias de seguridad, y su inmutabilidad es una propiedad del almacenamiento.
* A favor, porque la cuota se controla con operaciones atómicas de Redis sin bloquear filas de la base del motor en cada llamada.
* A favor, porque los tres tienen equivalentes gestionados con capa gratuita (por ejemplo Neon o Supabase, Cloudflare R2, Upstash), y la configuración por entorno permite cambiar de local a cloud sin tocar código.
* En contra, porque son tres servicios para operar, monitorear y levantar en `docker-compose`, en lugar de uno.
* En contra, porque Redis es el más discutible de los tres: el control de cuota podría hacerse en PostgreSQL. Se elige Redis porque la cuota se consulta en cada llamada desde varios procesos, y porque perder su estado no pone en riesgo el trabajo.

### Confirmación

* P0 cierra con `make up` levantando PostgreSQL, MinIO y Redis.
* P2 verifica que una corrida guarda su snapshot en el almacenamiento de objetos y que reprocesarla no lo sobrescribe.
* P4 cubre INV-1 con un test que intenta un segundo vínculo activo sobre la misma publicación.
* P3 incluye en la campaña de RNF-06 un cierre de Redis con trabajo pendiente, y verifica que no se pierde ninguna tarea.

## Ventajas y desventajas de las opciones

### Opción A: Solo PostgreSQL

* A favor, porque es un solo servicio para operar.
* A favor, porque todo queda en una sola transacción.
* En contra, porque unos 5,8 GB por mes de binarios inmutables por proveedor inflan la base, sus copias y su mantenimiento, sin aprovechar nada de lo relacional.
* En contra, porque la cuota en una tabla obliga a bloquear una fila por tienda en cada llamada, desde varios procesos.

### Opción B: PostgreSQL, almacenamiento de objetos y Redis

* A favor, porque cada motor responde a una necesidad distinta y concreta.
* A favor, porque es la combinación con equivalentes cloud gratuitos más directos.
* En contra, porque suma dos servicios a operar.

### Opción C: PostgreSQL y Redis, snapshots en disco local

* A favor, porque es simple de implementar.
* En contra, porque deja estado importante en el disco de un contenedor, en contra de RNF-11.
* En contra, porque un snapshot local no está disponible para otro proceso ni para el pipeline de ML si corre en otro lado.

### Opción D: MongoDB para todo

* A favor, porque guarda documentos y binarios en un mismo motor.
* En contra, porque las invariantes entre vínculos, publicaciones y tareas se expresan mejor con restricciones relacionales.
* En contra, porque no resuelve mejor que la opción B ni los snapshots ni la cuota.

## Más información

* Relacionado con RF-20, RF-24, RF-27, RF-30, RF-39, RF-46, RF-48, RNF-06, RNF-10, RNF-11 y RNF-20.
* La forma de la cola de tareas dentro de PostgreSQL se decide en ADR-0006. El intercambio entre las dos bases, en ADR-0007.
