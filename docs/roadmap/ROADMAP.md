# Roadmap

**Entrega 1 aprobada. Devolución de la cátedra incorporada**

Este roadmap define el orden de construcción hacia el POC y el MVP.

## Criterios que ordenan el plan

1. **El riesgo primero.** El motor contra la cuota de la API se resuelve antes que cualquier funcionalidad de interfaz.
2. **El simulador antes que el motor.** Sin él no hay forma de ejercitar los caminos de falla.
3. **Un proveedor por una tienda antes de N por K.**
4. **CI y tests desde el primer hito.** No se incorporan al final.
5. **Continuidad sin pérdida de trabajo.** La interfaz con su API y el motor se ejecutan de forma independiente (RNF-20). Las caídas se prueban con trabajo pendiente desde el POC (RNF-06). El objetivo de disponibilidad es 99 % en 24 horas para cada conjunto, con reanudación del motor en hasta 10 minutos (RNF-19).

# Entrega 2: POC + SRD

El riesgo más grande es el motor de sincronización contra la API: cuota, idempotencia y ciclo de vida de los tokens (R-01).

El POC lo resuelve sobre una ruta completa y angosta: **el proveedor real Celesa y una tienda simulada que implementa el contrato real de MercadoLibre**, con stock propagándose de punta a punta y estado operativo persistido por vínculo.

## P0: Fundaciones

**Qué se construye**

* Repo privado compartido con la cátedra.
* Estructura del repositorio en Python con FastAPI (ADR-0004), con un servicio por componente del motor y el simulador. La base de la API de consulta y su intercambio con el motor por replicación lógica (ADR-0007) se agregan en M1.
* `docker-compose` base con PostgreSQL, Redis y almacenamiento de objetos (ADR-0005).
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
* Validación de corrida con el coeficiente de CU-07 y cuarentena: una corrida sospechosa no modifica el estado vigente ni genera deltas.
* Consulta de corridas en cuarentena con su coeficiente, por línea de comandos.
* Generador de feeds.

**Requisitos**

* RF-04
* RF-06
* RF-07
* RF-08
* RF-20
* RF-21
* RF-22
* RF-28
* RF-37
* RNF-02

**Dependencias**

P0.

**Criterio de salida verificable**

* Una corrida real de aproximadamente 255.000 SKU se completa dentro del tiempo definido por RNF-02.
* Reejecutar la corrida no duplica efectos.
* Existen tests con las anomalías reales del feed, incluyendo duplicados e ISBN alfanuméricos.
* Una corrida truncada y una con ceros en masa, producidas por el generador de feeds, quedan en cuarentena con su coeficiente registrado, sin modificar el estado vigente ni generar deltas. Test en CI.
* `scripts/analizar_feed.py` se ejecuta sobre al menos dos pares de corridas reales consecutivas de Celesa y se registran `D`, `Z` y el coeficiente. Con ese resultado se fija el perfil de deltas de las pruebas de P3 y se verifica S-07.

## P3: Motor

**Qué se construye**

* Comparador.
* Cola con prioridad y envejecimiento.
* Reemplazo por vínculo.
* Worker de publicación con control de cuota.
* Reparto por tienda de 40 req/min para sincronización habitual y 20 para operaciones masivas, con préstamo del cupo ocioso hasta 60 en total.
* Reintentos con backoff.
* Dead letter persistida para errores no reintentables, con delta, respuesta de la API y fecha de falla, consultable por línea de comandos.
* Idempotencia.
* Estado operativo por vínculo y registros técnicos correlacionados por corrida y tarea.
* Conservación y recuperación de tareas pendientes y en curso, incluidas las órdenes de stock cero.
* Recuperación automática ante cierres abruptos.

**Requisitos**

* RF-23
* RF-24
* RF-25
* RF-26
* RF-27
* RF-30
* RF-45
* RF-46
* RNF-03 (ruta de un proveedor y una tienda)
* RNF-04
* RNF-06
* RNF-06b
* RNF-19 (reanudación del procesamiento)

**Dependencias**

P1 y P2.

**Criterio de salida verificable**

* Se prueba la propiedad `cola pendiente ≤ vínculos activos`.
* Reejecutar una corrida produce cero escrituras adicionales.
* Se puede consultar el último stock deseado, el último confirmado, la fecha del último éxito y el estado pendiente o en falla de cada vínculo (RF-30). Un intento fallido conserva el último confirmado. Actualizar el estado no elimina una falla pendiente ni su contexto. Los registros de trabajo permiten identificar los estados de las tareas y verificar RNF-03 y RNF-06.
* La campaña reproducible de RNF-06 ejecuta 10 cierres abruptos y recupera el 100 % del trabajo vigente, incluidas tareas en curso y órdenes de stock cero, sin duplicar efectos. Cubre también la caída del servicio de cola y los puntos de interrupción definidos en PRD §4.
* Después de cada cierre de un proceso del motor, el procesamiento se reanuda automáticamente en hasta 10 minutos desde la caída, con sus almacenes disponibles (RNF-19).
* Un 429 recibido de MercadoLibre conserva la actualización pendiente y se reintenta internamente. No genera una alerta al usuario, una dead letter ni un fallo persistente de publicación (RF-24).
* Con ambas clases pendientes se verifica 40/20. Con una sola, el préstamo del cupo libre hasta 60. Al reactivar la otra se restablece el reparto sin exceder el límite total.
* Una publicación cerrada y un token revocado, provocados con el simulador, terminan en dead letter con su delta, respuesta y fecha, y se consultan sin entrar a la base. La suma de deltas aplicados, en dead letter y descartados por cuarentena es igual a los deltas calculados (RNF-03). Tests en CI.

**Resolución de R-01.** Prueba reproducible contra el simulador con el límite real de 60 req/min, una tienda y una cola inicial de **3.000 tareas** repartidas en las tres prioridades, con nuevas corridas cada 30 minutos según el perfil de deltas medido en P2. Un observador externo registra llamadas y aplicaciones. R-01 queda resuelto si se cumplen las cuatro condiciones:

1. **Cero 429 provocados por exceso propio** durante toda la prueba. Los 429 que el simulador inyecta a propósito se cuentan aparte y se excluyen.
2. **Caudal sostenido de al menos el 95 % del cupo asignado** mientras la cola tenga trabajo: 57 llamadas por minuto con solo sincronización habitual (préstamo del cupo masivo) y 38 con ambas clases activas.
3. **Drenado predecible:** la cola de N tareas se vacía dentro de ±10 % de N dividido por el caudal asignado.
4. **Espera acotada para la prioridad baja:** ninguna tarea supera la espera máxima que el envejecimiento declara en el SRD.

## P4: Tiendas y vínculos

**Qué se construye**

* Alta de tienda mediante OAuth contra el simulador.
* Lectura de catálogo en dos etapas.
* Sugerencia y aprobación de vínculos por línea de comandos.
* ON/OFF con la regla de corte.
* Comparación inicial al vincular.

**Requisitos**

* RF-11
* RF-12
* RF-16
* RF-17
* RF-18
* RF-19
* RF-39
* RF-43
* RF-47

**Dependencias**

P1 y P3.

**Criterio de salida verificable**

* El flujo OAuth completo funciona contra el simulador.
* INV-1 está cubierta por un test.
* Apagar un vínculo deja la publicación en stock cero.

## P5: Cierre del POC

**Qué se construye**

* Flujo punta a punta desde Celesa real hasta una tienda simulada.
* Operación por línea de comandos: alta del proveedor, vinculación, disparo de la ingesta y consulta de estado operativo, dead letters y cuarentenas.
* README.
* ADRs.
* SRD sin Machine Learning.
* Video.

**Requisitos**

Entrega 2.

**Dependencias**

P2, P3 y P4.

**Criterio de salida verificable**

`make demo` reproduce el flujo completo, incluidos los escenarios de respuesta 429, token revocado, publicación cerrada en dead letter y corrida en cuarentena.

P1 y P2 pueden avanzar en paralelo porque no se conectan hasta P3.

Durante el POC se permite simplificar o mockear algunos componentes, siempre que quede declarado en el README. La consigna admite un POC con interfaz mínima o inexistente: el POC **no tiene interfaz gráfica** y se opera por línea de comandos, con disparo manual de la ingesta en lugar de la programación por proveedor. Las credenciales del feed y del simulador se toman de variables de entorno (RNF-07). La interfaz web, el login, el cifrado de secretos y la prueba de independencia de RNF-20 se construyen en M1. La dead letter (RF-27) y la cuarentena (RF-28) se implementan completas desde el POC: el usuario puede identificar qué vínculos no se actualizaron y qué corridas no se propagaron. Su vista en el tablero de salud llega con RF-31 en M6. En el POC se consultan por línea de comandos.

# Entrega 3: MVP

El objetivo del MVP es generalizar y operar la solución: N proveedores por K tiendas, el segundo formato de origen, catálogo vivo, gobernanza de corridas, observabilidad verificable y el componente de Machine Learning. La demostración comprometida fija **K = 2 tiendas simuladas** y una prueba de capacidad de **100.000 vínculos activos totales, 50.000 por tienda**. El perfil de deltas por corrida sigue pendiente de acordar y se documentará antes de medir RNF-01 y RNF-13.

## M1: N × K, interfaz y acceso

**Qué se construye**

* Interfaz web con su API, ejecutable de forma independiente del motor, con bases de datos y CPU separados.
* Login y control de acceso en todos los endpoints.
* Secretos cifrados.
* Varios proveedores y tiendas.
* Modificación y baja de proveedores.
* Frecuencia de ingesta configurable.
* Vista de tiendas.

**Requisitos**

* RF-01
* RF-03
* RF-09
* RF-10
* RF-15
* RNF-08
* RNF-20

**Dependencias**

P5.

**Criterio de salida verificable**

Se puede pasar de **1 a 2 tiendas simuladas sobre el mismo feed sin modificar código**, correspondiente al criterio de éxito 2. La segunda tienda reutiliza el estado vigente del proveedor sin duplicar su ingesta. Se verifica lectura de catálogo, sugerencia de vínculos y comienzo de la sincronización. La prueba de capacidad de 100.000 vínculos totales se completa en M8 (RNF-13). Agregar más tiendas exige nuevas mediciones.

Ningún endpoint de la API responde sin sesión, verificado con tests (RNF-08).

El test de RNF-20 demuestra los dos sentidos de la independencia: con la interfaz y su API detenidas, un cambio de una fuente ya configurada llega a la tienda. Con el motor detenido, la interfaz consulta su copia del estado y acepta una solicitud pendiente que se recupera al reanudarlo. Se documentan bases y CPU separados y se verifica que la consulta no necesite la base del motor.

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

* Alerta de errores de parseo.
* Publicaciones muertas.
* Estados `degradado` y `atrasada`.
* Baja de proveedor.
* Desconexión de tienda.
* Reproceso manual.

**Requisitos**

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
* Con N proveedores y K tiendas, la suma de estados terminales es igual a los deltas calculados, correspondiente al criterio de éxito 4. La ruta de un proveedor y una tienda ya se verificó en P3.
* Un proveedor con una corrida en cuarentena pasa a *degradado* y alerta, mientras los demás siguen operando.
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
* Cuota de la API detrás de la interfaz: 60 solicitudes por minuto por usuario, con rechazo 429 explícito al excederla.
* Cuota diaria por usuario de Ivo Stock: un alta o baja de proveedor o tienda y un lote de vinculación, con contadores compartidos entre sesiones y reintentos de la misma operación sin consumo duplicado.

**Requisitos**

* RF-41
* RF-55
* RNF-11
* RNF-16
* RNF-22

**Dependencias**

M1.

**Criterio de salida verificable**

* El pipeline construye y publica imágenes.
* El despliegue se demuestra.
* Los tests de RNF-22 verifican límite entre sesiones y entre la interfaz y la vía programática, `Retry-After`, conservación de la pantalla y mensaje «Demasiadas solicitudes. Reintentá en X segundos», sin generar trabajo por la petición rechazada.
* Los tests de RF-55 verifican ambas cuotas diarias con reloj controlado, renovación de día, identidad de los reintentos y rechazo sin efectos al agotarse el cupo.

## M8: Verificación y cierre

**Qué se construye**

* Medición de RNF-01.
* Medición de RNF-14.
* Medición de RNF-13 con **100.000 vínculos activos totales en 2 tiendas simuladas, 50.000 por tienda**, registrando el perfil de carga acordado y los recursos de ejecución.
* Medición de RNF-19: prueba continua de 24 horas, con al menos 99 % de disponibilidad por separado para la interfaz con su API y para el motor, según las sondas externas de PRD §4.
* Medición de RNF-21: 1.000 usuarios a una consulta por segundo cada uno durante 30 minutos, con p95 menor a 2 segundos y el motor activo, según PRD §4. La evidencia documenta bases y CPU separados y comprueba la coexistencia con RNF-01 y RNF-02 bajo el perfil de sincronización acordado.
* Verificación de la cuota propia de RNF-22 y del tratamiento separado de 429 propios y de MercadoLibre.
* Evidencia de las pruebas de conservación, recuperación e independencia de RNF-06, RNF-19 y RNF-20.
* Verificación de los **6 criterios de éxito vigentes**. El criterio 7 y CU-09 fueron retirados al recortar el historial completo, según PRD §5.
* SRD completo con Machine Learning.
* ADRs.
* Video.

**Requisitos**

Entrega 3.

**Dependencias**

Todos los hitos anteriores.

**Criterio de salida verificable**

Se completa una tabla que relaciona cada criterio con su evidencia de forma completa y reproducible. Se adjunta el registro de sondas de RNF-19, separado de las fallas de proveedores y marketplace. Las caídas de componentes y almacenes propios dentro de la ventana cuentan como indisponibilidad.

RNF-13 se documenta en el SRD de cada entrega y su prueba de capacidad se completa en M8. El POC conserva una ruta reducida de un proveedor y una tienda. No se le exige demostrar todavía el volumen completo del MVP. La evidencia de M8 distingue cantidad de vínculos y deltas por corrida, y no extrapola capacidad a más tiendas sin mediciones.

# Calendario y responsables

Cada hito tiene un **responsable principal**, que responde por su criterio de salida, y un **integrante de apoyo**, que revisa sus cambios. Los hitos compartidos se reparten entre los tres. El **tamaño** es relativo entre hitos (chico, mediano o grande) y muestra dónde se concentra el esfuerzo. Las fechas siguen el calendario de la cátedra: **Entrega 2 el 27 de octubre** y **Entrega 3 el 24 de noviembre**, junto con la presentación oral.

| Hito | Responsable principal | Apoyo | Tamaño | Fecha objetivo |
|---|---|---|---|---|
| P0 Fundaciones | Compartido | Ninguno | Chico | 22/10 |
| P1 Simulador y marketplace | Francisco Ortega | Sofía Ramos | Mediano | 24/10 |
| P2 Ingesta y cuarentena | María Saráchaga | Sofía Ramos | Mediano | 24/10 |
| P3 Motor y dead letter | Sofía Ramos | Francisco Ortega | Grande | 26/10 |
| P4 Tiendas y vínculos | Francisco Ortega | María Saráchaga | Mediano | 26/10 |
| P5 Cierre del POC | Compartido | Ninguno | Mediano | **27/10, Entrega 2** |
| M1 N × K, interfaz y acceso | María Saráchaga | Francisco Ortega | Grande | 3/11 |
| M2 Segundo formato | María Saráchaga | Sofía Ramos | Chico | 3/11 |
| M3 Catálogo vivo | Francisco Ortega | Sofía Ramos | Mediano | 3/11 |
| M4 Gobernanza y degradación | Sofía Ramos | María Saráchaga | Mediano | 10/11 |
| M7 Programático, cloud y cuotas propias | Francisco Ortega | María Saráchaga | Mediano | 10/11 |
| M5 Machine Learning | María Saráchaga | Sofía Ramos | Grande | 17/11 |
| M6 Observabilidad | Sofía Ramos | Francisco Ortega | Mediano | 17/11 |
| M8 Verificación y cierre | Compartido | Ninguno | Grande | **24/11, Entrega 3** |

**Paralelismo.** Cada integrante lleva un hito por vez en cada tramo: P1 y P2 en paralelo, después P3 y P4. En el MVP, M1, M2 y M3 en la primera semana, M4 y M7 en la segunda, M5 y M6 en la tercera, y la última semana queda para M8, el video y la presentación oral. La prueba continua de 24 horas de RNF-19 se programa al comienzo de esa semana, para poder repetirla si falla.

**El tramo más exigente es el POC**, con seis días entre la revisión de la devolución y la Entrega 2. Por eso el POC se opera por línea de comandos, como admite la consigna, y su plan B está definido abajo.

**Seguimiento.** Al cierre de cada hito se registra la fecha real contra la objetivo. Si un hito se atrasa más de dos días, se aplica el orden de recorte antes de empezar el tramo siguiente, no al final de la cursada.

# Control, plan B y orden de recorte

## Control de cada hito

Cada hito cierra con tests, README actualizado y, cuando exista una decisión estructural, un ADR que compare alternativas.

Al inicio de cada bloque se incorporan las correcciones realizadas por la cátedra sobre la entrega anterior.

## Puntos de control

**Fin de P1**

Si el simulador no reproduce la semántica de cuota, no se avanza a P3.

**Fin de P3**

R-01 debe quedar resuelto según las cuatro condiciones de P3. En caso contrario se replantea el objetivo de latencia antes de empezar P4.

**Inicio de M5**

Si existen pocas corridas archivadas, el modelo comienza en modo sombra y el baseline continúa tomando la decisión, según RF-50.

## Plan B del POC

La consigna admite un POC con interfaz mínima o inexistente.

El POC ya se plantea sin interfaz gráfica. Si al 26 de octubre P4 no está cerrado, la tienda de la demostración se conecta con un token emitido por el simulador en lugar del flujo OAuth completo, y los vínculos se crean aceptando todas las sugerencias por SKU. El POC se cierra sobre el motor construido entre P1 y P3 con datos reales, y el README declara la simplificación. El flujo OAuth completo pasa a M1.

## Orden de recorte del MVP

Si el tiempo disponible no alcanza, el orden de recorte previsto desde lo primero que se elimina hasta lo último es el siguiente:

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
