# Roadmap

**Entrega 1: Diseño**

Este roadmap define el orden de construcción hacia el POC y el MVP.

## Criterios que ordenan el plan

1. **El riesgo primero.** El motor contra la cuota de la API se resuelve antes que cualquier funcionalidad de interfaz.
2. **El simulador antes que el motor.** Sin él no hay forma de ejercitar los caminos de falla.
3. **Un proveedor por una tienda antes de N por K.**
4. **CI y tests desde el primer hito.** No se incorporan al final.

# Entrega 2: POC + SRD

El riesgo más grande es el motor de sincronización contra la API: cuota, idempotencia y ciclo de vida de los tokens (R-01).

El POC lo resuelve sobre una ruta completa y angosta: **el proveedor real Celesa y una tienda simulada que implementa el contrato real de MercadoLibre**, con stock propagándose de punta a punta y auditado.

## P0: Fundaciones

**Qué se construye**

* Repo privado compartido con la cátedra.
* Estructura de servicios.
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
* Reintentos con backoff.
* Idempotencia.
* Auditoría.

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

**Dependencias**

P1 y P2.

**Criterio de salida verificable**

* Se prueba la propiedad `cola pendiente ≤ vínculos activos`.
* Reejecutar una corrida produce cero escrituras adicionales.
* La auditoría puede consultarse por publicación.

## P4: Tiendas y vínculos

**Qué se construye**

* Login.
* Secretos cifrados.
* Alta de tienda mediante OAuth.
* Lectura de catálogo en dos etapas.
* Sugerencia y aprobación de vínculos.
* ON/OFF con la regla de corte.
* Comparación inicial al vincular.

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

**Dependencias**

P1 y P3.

**Criterio de salida verificable**

* El flujo OAuth completo funciona contra el simulador.
* INV-1 está cubierta por un test.
* Apagar un vínculo deja la publicación en stock cero.

## P5: Cierre del POC

**Qué se construye**

* Flujo punta a punta desde Celesa real hasta una tienda simulada.
* Interfaz mínima.
* README.
* ADRs.
* SRD sin Machine Learning.
* Video.

**Requisitos**

Entrega 2.

**Dependencias**

P2, P3 y P4.

**Criterio de salida verificable**

`make demo` reproduce el flujo completo, incluidos los escenarios de respuesta 429 y token revocado.

P1 y P2 pueden avanzar en paralelo porque no se conectan hasta P3.

Durante el POC se permite simplificar o mockear algunos componentes, siempre que quede declarado en el README. Se admite una interfaz mínima, el disparo manual de la ingesta en lugar de la programación por proveedor y dead letters registradas como fallo terminal en la auditoría. RF-27 completo se incorpora en M4 para garantizar que ningún delta quede sin estado terminal.

# Entrega 3: MVP

El objetivo del MVP es generalizar y operar la solución: N proveedores por K tiendas, el segundo formato de origen, catálogo vivo, gobernanza de corridas, observabilidad verificable y el componente de Machine Learning.

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

Se puede pasar de una tienda a K tiendas sobre el mismo feed sin modificar código, correspondiente al criterio de éxito 2.

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

Un test demuestra que una lectura de catálogo disparada manualmente cede ante las escrituras de stock pendientes.

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
* Verificación de los 7 criterios de éxito.
* SRD completo con Machine Learning.
* ADRs.
* Video.

**Requisitos**

Entrega 3.

**Dependencias**

Todos los hitos anteriores.

**Criterio de salida verificable**

Se completa una tabla que relaciona cada criterio con su evidencia de forma completa y reproducible.

RNF-13, correspondiente a escalabilidad conocida, se argumenta en el SRD de cada entrega y no tiene un hito propio.

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
