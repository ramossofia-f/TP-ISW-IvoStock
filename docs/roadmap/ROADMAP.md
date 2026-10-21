# Roadmap

**Entrega 1 aprobada; revisión del diseño en curso**

Este roadmap define el orden de construcción hacia el POC y el MVP.

## Criterios que ordenan el plan

1. **El riesgo primero.** El motor contra la cuota de la API se resuelve antes que cualquier funcionalidad de interfaz.
2. **El simulador antes que el motor.** Sin él no hay forma de ejercitar los caminos de falla.
3. **Un proveedor por una tienda antes de N por K.**
4. **CI y tests desde el primer hito.** No se incorporan al final.
5. **Continuidad sin pérdida de trabajo.** La interfaz con su API y el motor se ejecutan de forma independiente (RNF-20); las caídas se prueban con trabajo pendiente desde el POC (RNF-06). El objetivo de disponibilidad es 99 % en 24 horas para cada conjunto, con reanudación del motor en hasta 10 minutos (RNF-19).

# Entrega 2: POC + SRD

El riesgo más grande es el motor de sincronización contra la API: cuota, idempotencia y ciclo de vida de los tokens (R-01).

El POC lo resuelve sobre una ruta completa y angosta: **el proveedor real Celesa y una tienda simulada que implementa el contrato real de MercadoLibre**, con stock propagándose de punta a punta y estado operativo persistido por vínculo.

## P0: Fundaciones

**Qué se construye**

* Repo privado compartido con la cátedra.
* Estructura de servicios con ejecución, bases de datos y CPU independientes para la API de consulta y el motor; intercambio asíncrono y durable, sin llamadas directas. El mecanismo se justificará en un ADR posterior.
* `docker-compose` base con PostgreSQL, Redis y almacenamiento de objetos.
* CI con build, tests y chequeo de secretos.
* Plantilla de ADR.

**Requisitos**

* RNF-07
* RNF-10
* RNF-12

**Dependencias**

Ninguna.

**Criterio de salida verificable**

* CI en verde sobre `main`.
* `make up` levanta la infraestructura.
* El historial muestra commits de cada integrante.

## P1: Simulador y marketplace

**Qué se construye**

* Interfaz de marketplace.
* Simulador con OAuth 2.0 completo.
* Catálogo paginado.
* Escritura de stock con pausa por `out_of_stock`.
* Cuota de 60 requests por minuto con respuesta 429.
* Errores reintentables y no reintentables.
* Generador de catálogo.

**Requisitos**

* RF-35
* RF-36
* RF-38

**Dependencias**

P0.

**Criterio de salida verificable**

* Contract tests en verde.
* Se obtiene una respuesta 429 al superar la cuota.
* Puede provocarse a demanda la revocación de un token a mitad de una corrida.

## P2: Ingesta

**Qué se construye**

* Alta de proveedor `.csv` con preview y fetch de prueba.
* Corrida contra Celesa real.
* Snapshot crudo e inmutable.
* Normalización.
* Estado vigente mediante UPSERT.
* Generador de feeds.

**Requisitos**

* RF-04
* RF-06
* RF-07
* RF-08
* RF-20
* RF-21
* RF-22
* RF-37
* RNF-02

**Dependencias**

P0.

**Criterio de salida verificable**

* Una corrida real de aproximadamente 255.000 SKU se completa dentro del tiempo definido por RNF-02.
* Reejecutar la corrida no duplica efectos.
* Existen tests con las anomalías reales del feed, incluyendo duplicados e ISBN alfanuméricos.

## P3: Motor

**Qué se construye**

* Comparador.
* Cola con prioridad y envejecimiento.
* Reemplazo por vínculo.
* Worker de publicación con control de cuota.
* Reparto por tienda de 40 req/min para sincronización habitual y 20 para operaciones masivas, con préstamo del cupo ocioso hasta 60 en total.
* Reintentos con backoff.
* Idempotencia.
* Estado operativo por vínculo y registros técnicos correlacionados por corrida y tarea.
* Conservación y recuperación de tareas pendientes y en curso, incluidas las órdenes de stock cero.
* Recuperación automática ante cierres abruptos.

**Requisitos**

* RF-23
* RF-24
* RF-25
* RF-26
* RF-30
* RF-45
* RF-46
* RNF-04
* RNF-06
* RNF-06b
* RNF-19 (reanudación del procesamiento)

**Dependencias**

P1 y P2.

**Criterio de salida verificable**

* Se prueba la propiedad `cola pendiente ≤ vínculos activos`.
* Reejecutar una corrida produce cero escrituras adicionales.
* Se puede consultar el último stock deseado, el último confirmado, la fecha del último éxito y el estado pendiente o en falla de cada vínculo (RF-30). Un intento fallido conserva el último confirmado; actualizar el estado no elimina una falla pendiente ni su contexto. Los registros de trabajo permiten identificar los estados de las tareas y verificar RNF-03 y RNF-06.
* La campaña reproducible de RNF-06 ejecuta 10 cierres abruptos y recupera el 100 % del trabajo vigente, incluidas tareas en curso y órdenes de stock cero, sin duplicar efectos. Cubre también la caída del servicio de cola y los puntos de interrupción definidos en PRD §4.
* Después de cada cierre de un proceso del motor, el procesamiento se reanuda automáticamente en hasta 10 minutos desde la caída, con sus almacenes disponibles (RNF-19).
* Un 429 recibido de MercadoLibre conserva la actualización pendiente y se reintenta internamente; no genera una alerta al usuario, una dead letter ni un fallo persistente de publicación (RF-24).
* Con ambas clases pendientes se verifica 40/20; con una sola, el préstamo del cupo libre hasta 60; al reactivar la otra se restablece el reparto sin exceder el límite total.

## P4: Tiendas y vínculos

**Qué se construye**

* Login.
* Secretos cifrados.
* Alta de tienda mediante OAuth.
* Lectura de catálogo en dos etapas.
* Sugerencia y aprobación de vínculos.
* ON/OFF con la regla de corte.
* Comparación inicial al vincular.
* Cuota de la API detrás de la interfaz: 60 solicitudes por minuto por usuario, con rechazo 429 explícito al excederla.
* Cuota diaria por usuario de Ivo Stock: un alta o baja de proveedor o tienda y un lote de vinculación, con contadores compartidos entre sesiones y reintentos de la misma operación sin consumo duplicado.

**Requisitos**

* RF-01
* RF-03
* RF-11
* RF-12
* RF-16
* RF-17
* RF-18
* RF-19
* RF-39
* RF-43
* RF-47
* RNF-08
* RNF-22
* RF-55

**Dependencias**

P1 y P3.

**Criterio de salida verificable**

* El flujo OAuth completo funciona contra el simulador.
* INV-1 está cubierta por un test.
* Apagar un vínculo deja la publicación en stock cero.
* Los tests de RNF-22 verifican límite entre sesiones, `Retry-After`, conservación de la pantalla y mensaje «Demasiadas solicitudes; reintentá en X segundos», sin generar trabajo por la petición rechazada.
* Los tests de RF-55 verifican ambas cuotas diarias con reloj controlado, renovación de día, identidad de los reintentos y rechazo sin efectos al agotarse el cupo.

## P5: Cierre del POC

**Qué se construye**

* Flujo punta a punta desde Celesa real hasta una tienda simulada.
* Interfaz mínima con su API, ejecutable de forma independiente del motor.
* README.
* ADRs.
* SRD sin Machine Learning.
* Video.

**Requisitos**

Entrega 2 y RNF-20.

**Dependencias**

P2, P3 y P4.

**Criterio de salida verificable**

`make demo` reproduce el flujo completo, incluidos los escenarios de respuesta 429 y token revocado.

El test de RNF-20 demuestra los dos sentidos de la independencia: con la interfaz y su API detenidas, un cambio de una fuente ya configurada llega a la tienda; con el motor detenido, la interfaz consulta su copia del estado y acepta una solicitud pendiente que se recupera al reanudarlo. Se documentan bases y CPU separados y se verifica que la consulta no necesite la base del motor.

P1 y P2 pueden avanzar en paralelo porque no se conectan hasta P3.

Durante el POC se permite simplificar o mockear algunos componentes, siempre que quede declarado en el README. Se admite una interfaz mínima, el disparo manual de la ingesta en lugar de la programación por proveedor y dead letters registradas como fallo terminal persistido con su delta, respuesta y fecha de falla en el registro de trabajo. RF-27 completo se incorpora en M4 para garantizar que ningún delta quede sin estado terminal. La revisión de ese alcance y de la cuarentena desde el POC sigue pendiente en el punto 7 de la devolución; el recorte del historial completo no modifica sus garantías.

# Entrega 3: MVP

El objetivo del MVP es generalizar y operar la solución: N proveedores por K tiendas, el segundo formato de origen, catálogo vivo, gobernanza de corridas, observabilidad verificable y el componente de Machine Learning. La demostración comprometida fija **K = 2 tiendas simuladas** y una prueba de capacidad de **100.000 vínculos activos totales, 50.000 por tienda**. El perfil de deltas por corrida sigue pendiente de acordar y se documentará antes de medir RNF-01 y RNF-13.

## M1: N × K

**Qué se construye**

* Varios proveedores y tiendas.
* Modificación y baja de proveedores.
* Frecuencia de ingesta configurable.
* Vista de tiendas.

**Requisitos**

* RF-09
* RF-10
* RF-15

**Dependencias**

P5.

**Criterio de salida verificable**

Se puede pasar de **1 a 2 tiendas simuladas sobre el mismo feed sin modificar código**, correspondiente al criterio de éxito 2. La segunda tienda reutiliza el estado vigente del proveedor sin duplicar su ingesta; se verifica lectura de catálogo, sugerencia de vínculos y comienzo de la sincronización. La prueba de capacidad de 100.000 vínculos totales se completa en M8 (RNF-13); agregar más tiendas exige nuevas mediciones.

## M2: Segundo formato

**Qué se construye**

Proveedor sobre tabla PostgreSQL.

**Requisitos**

RF-05.

**Dependencias**

P5.

**Criterio de salida verificable**

Se puede dar de alta un proveedor nuevo en menos de 10 minutos y sin escribir código, correspondiente al criterio de éxito 1.

## M3: Catálogo vivo

**Qué se construye**

* Webhooks de publicación nueva.
* Carga manual de IDs.
* Cuota compartida por tienda.

**Requisitos**

* RF-13
* RF-14
* RF-48

**Dependencias**

P5.

**Criterio de salida verificable**

Un test demuestra que lectura de catálogo y escritura de stock comparten el límite de 60 req/min por tienda, se imputan a su clase y respetan 40/20 cuando ambas tienen trabajo pendiente. También verifica préstamo del cupo ocioso y retorno al reparto sin desplazar el presupuesto reservado a sincronización habitual.

## M4: Gobernanza y degradación

**Qué se construye**

* Validación y cuarentena por corrida.
* Alerta de errores de parseo.
* Dead letters.
* Publicaciones muertas.
* Estados `degradado` y `atrasada`.
* Baja de proveedor.
* Desconexión de tienda.
* Reproceso manual.

**Requisitos**

* RF-27
* RF-28
* RF-29
* RF-32
* RF-34
* RF-40
* RF-42
* RF-44
* RNF-03
* RNF-05

**Dependencias**

M1.

**Criterio de salida verificable**

* Los tres casos del criterio de éxito 6 pueden provocarse mediante el simulador.
* La suma de estados terminales es igual a los deltas calculados, correspondiente al criterio de éxito 4.
* Una tienda atrasada continúa drenando trabajo y una tienda degradada no.

## M5: Machine Learning

**Qué se construye**

* Dataset versionado desde el histórico de snapshots.
* Entrenamiento reproducible.
* Evaluación contra el baseline.
* Serving con fallback.
* Monitoreo.

**Requisitos**

* RF-49 a RF-53
* RNF-17
* RNF-18

**Dependencias**

M4 y disponibilidad de histórico suficiente.

**Criterio de salida verificable**

* `make train` reproduce las métricas.
* El modelo corre en modo sombra sobre corridas reales.
* El fallback al baseline está probado.

## M6: Observabilidad

**Qué se construye**

* Logging estructurado con identificador de corrida.
* Métricas por feed y por tienda.
* Health checks.
* Tablero de salud.

**Requisitos**

* RF-31
* RF-33
* RNF-09

**Dependencias**

M4.

**Criterio de salida verificable**

El tablero muestra latencia, dead letters y estados de excepción.

## M7: Programático y cloud

**Qué se construye**

* API descrita mediante OpenAPI.
* Imágenes construidas en CI.
* Configuración por entorno.
* Despliegue efímero en free tier.

**Requisitos**

* RF-41
* RNF-11
* RNF-16

**Dependencias**

M1.

**Criterio de salida verificable**

* El pipeline construye y publica imágenes.
* El despliegue se demuestra.

## M8: Verificación y cierre

**Qué se construye**

* Medición de RNF-01.
* Medición de RNF-14.
* Medición de RNF-13 con **100.000 vínculos activos totales en 2 tiendas simuladas, 50.000 por tienda**, registrando el perfil de carga acordado y los recursos de ejecución.
* Medición de RNF-19: prueba continua de 24 horas, con al menos 99 % de disponibilidad por separado para la interfaz con su API y para el motor, según las sondas externas de PRD §4.
* Medición de RNF-21: 1.000 usuarios a una consulta por segundo cada uno durante 30 minutos, con p95 menor a 2 segundos y el motor activo, según PRD §4. La evidencia documenta bases y CPU separados y comprueba la coexistencia con RNF-01 y RNF-02 bajo el perfil de sincronización acordado.
* Verificación de la cuota propia de RNF-22 y del tratamiento separado de 429 propios y de MercadoLibre.
* Evidencia de las pruebas de conservación, recuperación e independencia de RNF-06, RNF-19 y RNF-20.
* Verificación de los **6 criterios de éxito vigentes**; el criterio 7 y CU-09 fueron retirados al recortar el historial completo, según PRD §5.
* SRD completo con Machine Learning.
* ADRs.
* Video.

**Requisitos**

Entrega 3.

**Dependencias**

Todos los hitos anteriores.

**Criterio de salida verificable**

Se completa una tabla que relaciona cada criterio con su evidencia de forma completa y reproducible. Se adjunta el registro de sondas de RNF-19, separado de las fallas de proveedores y marketplace. Las caídas de componentes y almacenes propios dentro de la ventana cuentan como indisponibilidad.

RNF-13 se documenta en el SRD de cada entrega y su prueba de capacidad se completa en M8. El POC conserva una ruta reducida de un proveedor y una tienda; no se le exige demostrar todavía el volumen completo del MVP. La evidencia de M8 distingue cantidad de vínculos y deltas por corrida, y no extrapola capacidad a más tiendas sin mediciones.

# Control, plan B y orden de recorte

## Control de cada hito

Cada hito cierra con tests, README actualizado y, cuando exista una decisión estructural, un ADR que compare alternativas.

Al inicio de cada bloque se incorporan las correcciones realizadas por la cátedra sobre la entrega anterior.

## Puntos de control

**Fin de P1**

Si el simulador no reproduce la semántica de cuota, no se avanza a P3.

**Fin de P3**

R-01 debe quedar resuelto. En caso contrario se replantea el objetivo de latencia.

**Inicio de M5**

Si existen pocas corridas archivadas, el modelo comienza en modo sombra y el baseline continúa tomando la decisión, según RF-50.

## Plan B del POC

La consigna admite un POC con interfaz mínima o inexistente.

Si al cerrar P4 el tiempo disponible no alcanza, las acciones correspondientes a RF-06 y RF-17 se ejecutan mediante API o línea de comandos en lugar de una interfaz gráfica.

En ese caso, el POC se cierra sobre el motor construido entre P1 y P3 utilizando datos reales.

## Orden de recorte del MVP

Si el tiempo disponible no alcanza, el orden de recorte previsto desde lo primero que se elimina hasta lo último es:

1. RF-34
2. RF-41 y RNF-16
3. RF-10
4. RF-09
5. RF-42
6. RF-32
7. RF-14
8. RF-44

RF-40 no forma parte de esta lista porque es el único requisito que verifica INV-3. Recortarlo dejaría una invariante heredada sin demostrar.

Ningún requisito clasificado como Must se recorta sin volver a validar el cambio con la cátedra.
