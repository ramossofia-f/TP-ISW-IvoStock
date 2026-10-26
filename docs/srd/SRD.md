# SRD: Ivo Stock

El [PRD](../prd/PRD.md) define el alcance y sus IDs. Este documento especifica implementación y comprobación. Los comandos están en el [README](../../README.md).

## Arquitectura

```mermaid
flowchart LR
    CLI[CLI / aplicación] --> PG[(PostgreSQL)]
    HTTP[Feed HTTP] --> I[Ingesta]
    I --> S3[(MinIO / S3)]
    I --> PG
    PG --> C[Comparación]
    C --> PG
    PG --> P[Publicación]
    P -->|HTTP y cuota| SIM[Marketplace simulado]
    SIM --> DB[(Tablas del simulador)]
    API[API] --> PG
```

Python 3.12, FastAPI, SQLAlchemy, Alembic, psycopg, httpx y boto3. Las dependencias se bloquean en `uv.lock`. API y workers comparten PostgreSQL; no se llaman entre sí. Sus caídas son independientes mientras PostgreSQL esté disponible. El simulador persiste en tablas propias y el motor sólo lo consulta por HTTP.

La CLI y los workers acceden a los servicios mediante `ivostock.services`. La ingesta reside en `ivostock.ingesta.servicio`, el parser y la guarda en `ivostock.ingesta`, la comparación en `ivostock.comparison`, el publicador en `ivostock.publisher` y el catálogo HTTP en `ivostock.marketplace`. El POC no expone operaciones de configuración por la API; su endpoint es `GET /health`. La interfaz autenticada corresponde al MVP.

## Persistencia y transacciones

| Entidad | Responsabilidad |
|---|---|
| providers, stores, catalog | Configuración, próxima ingesta y catálogo importado |
| runs, stock | Snapshot, resultado y último inventario completo aceptado |
| links | Asignación, deseado, confirmado, revisión, corte y estado |
| comparison_events | Aviso durable creado en el commit de aceptación |
| tasks | Una pendiente por vínculo; antigüedad, valor, revisión, backoff y lease |
| attempts, dead_letters | Evidencia de cada envío y fallas que requieren revisión |
| market_calls | Ventana móvil de permisos por tienda |
| worker_heartbeats | Actividad reciente de cada proceso |
| sim_* | Catálogo, cantidades, cuota y fallas del simulador |

Alembic instala el esquema. Un índice único parcial sobre publicación/tienda impide más de un vínculo no desactivado. Las cantidades son enteros entre 0 y 2.147.483.647. Los SKU son cadenas. Los snapshots usan claves SHA-256 y escritura condicional: los bytes de una clave existente no se reemplazan. Tareas e intentos conservan la referencia de corrida; un corte o una reanudación manual puede tener referencia nula y se identifica por vínculo y revisión.

La ingesta adquiere un advisory lock de sesión por proveedor, descarga, almacena el snapshot y registra su referencia. Después normaliza y evalúa el inventario. El reemplazo de stock, resultado aceptado y evento de comparación comparten una transacción. Se usa una tabla temporal con COPY y ANALYZE; sólo se actualizan cantidades distintas y los ausentes se eliminan mediante anti-join indexado. Un snapshot almacenado sin aceptación no cambia stock ni genera tareas. La siguiente corrida identifica registros abandonados como interrumpidos.

Una descarga idéntica al último snapshot aceptado reutiliza el inventario vigente; registra la corrida y conserva un evento durable de comparación. La guarda se calcula cuando cambia el snapshot. Los descartes de duplicados identifican la ocurrencia sustituida y nunca la fila ganadora.

La programación persiste `next_run_at`. Una ejecución automática vencida lo adelanta 300 minutos; una manual no lo modifica. El lock evita solapamientos. Una corrida automática interrumpida se recupera mediante el tratamiento de corridas abandonadas antes de esperar el siguiente vencimiento.

El comparador toma el mismo lock por proveedor. Lee su inventario vigente y los vínculos, actualiza deseados y encola diferencias, marcando eventos procesados en la misma transacción. Los vínculos en falla actualizan su deseado pero no vuelven a encolarse solos. Los cortes conservan deseado cero aunque una ingesta posterior tenga cantidad positiva.

## Cola y concurrencia

Las tareas disponibles se eligen por `enqueued_at, link_id`. El reemplazo conserva la fecha original e incrementa su contador; una nueva cantidad recibe una nueva revisión. Las tareas en backoff no impiden elegir otras disponibles. Una tarea en vuelo no se borra al cambiar el deseado.

Un lock de sesión por tienda serializa importación y publicación. El claim persiste revisión y lease antes del HTTP. El lease normal es de treinta segundos, mayor que el timeout HTTP de diez segundos del simulador controlado. Al caer un proceso, PostgreSQL libera su lock y otro puede recuperar la tarea cuando vence el lease. La campaña usa un lease de un segundo con peticiones pequeñas controladas.

La respuesta se confirma en una transacción con el vínculo bloqueado. Siempre se registra el valor realmente confirmado; sólo se retira la tarea si corresponde a la revisión enviada. Si apareció otra revisión, permanece pendiente. Una confirmación de cero sólo desactiva cuando corresponde a la intención vigente. Esta garantía se evalúa frente al simulador del proyecto, no frente a un servidor que difiera escrituras arbitrariamente después del timeout.

Una caída puede repetir una petición aceptada pero no confirmada localmente. La cantidad absoluta hace idempotente el efecto; la evidencia distingue intentos de efectos finales. La conservación se mide sobre trabajo vigente y registra reemplazos deliberados.

## Cuota y errores

Cada permiso de negocio se registra antes del HTTP en PostgreSQL. Un advisory lock transaccional por tienda protege limpieza, conteo e inserción de la ventana móvil de sesenta segundos. Se conceden como máximo sesenta permisos. Un permiso desperdiciado por una caída no se recupera anticipadamente. El simulador tiene un contador independiente para comprobar al cliente.

| Resultado | Tratamiento |
|---|---|
| 200 | Confirmar cantidad y fecha; completar revisión o conservar su reemplazo |
| 429 | Esperar `Retry-After` en segundos; conservar tarea sin gastar intentos de error |
| Sin conexión, timeout, 401 o 403 | Tienda degradada; conservar pendientes y probar acceso después de treinta segundos |
| 5xx | Hasta cinco intentos, con esperas de 5, 10, 20 y 40 segundos |
| Definitivo o agotado | Dead letter y vínculo en falla; reanudación explícita |

La CLI reanuda con el inventario actual, respetando un corte. Marca la revisión humana de las fallas sin borrarlas. Una falla de fuente congela esa fuente; la cuarentena tampoco convierte por sí sola la oferta a cero.

## Contratos HTTP y operación

El contrato del proveedor es RF-11. La preparación agrega exactamente los bytes `SKU;stock\n` al original, conserva procedencia y hashes y sirve únicamente el directorio de derivados. Las credenciales se configuran por entorno; las URLs no deben incluir secretos.

| Endpoint del simulador | Contrato |
|---|---|
| `GET /stores/{store}/items` | Bearer preconfigurado; `limit` entero de 1 a 100 (por defecto 100) y `offset` entero desde 0 (por defecto 0). Ordena por ID de publicación; devuelve `items` y `next_offset` (`null` al terminar) |
| `PUT /stores/{store}/items/{item}/stock` | Bearer; JSON `available_quantity` entero no negativo; cantidad absoluta |
| `POST /admin/seed` | Credencial de control; crea catálogo una vez por tienda |
| `POST /admin/fault` | Credencial de control; estado HTTP e intentos afectados, por tienda o publicación |
| `GET /admin/stores/{store}` | Observación externa de ensayos, sin consumir cuota de negocio |
| `GET /health` | Disponibilidad de proceso y esquema, sin datos de negocio |

El cero se observa como `out_of_stock`; una cantidad positiva como `active`. Los controles administrativos nunca son usados por el publicador. Las lecturas por la API de negocio sí consumen cuota. OpenAPI se obtiene de `/openapi.json` de cada aplicación.

La CLI devuelve JSON y códigos de salida no nulos para errores. Los registros no imprimen URL, tokens ni excepciones HTTP con credenciales. Cada corrida puede seguirse mediante su proveedor, evento, vínculo, revisión e intento.

El generador `ivostock.generador.feeds` produce escenarios sintéticos con semilla y manifiesto de parámetros/hashes; no modifica el inventario usado como base. Los logs de ingesta se formatean mediante `ivostock.logs`: mantienen contexto operativo y omiten el mensaje y traceback de excepciones externas. La CLI conserva su resultado JSON en stdout y envía estos diagnósticos a stderr.

## Protocolos de verificación

Las pruebas unitarias cubren RF-11 a RF-14. La integración usa un PostgreSQL real separado, `ivostock_test`, un bucket `snapshots-test`, servidor HTTP de feeds y simulador por TCP. Cubre RF-05 a RF-24 y RNF-03 a RNF-06. Cada prueba limpia únicamente su base de ensayo.

La campaña de diez cierres mata procesos externos después de observar un marcador: snapshot durable, modificación sin commit, aceptación confirmada, evento tomado, encolado sin commit, comparación confirmada, tarea tomada, HTTP respondido, confirmación sin commit y corte persistido. Se recupera por los comandos normales y se compara el stock externo con el trabajo vigente, incluyendo ceros. Las fallas de aplicación no justifican dead letters en esa campaña. La caída abrupta del servicio PostgreSQL se verifica además con su volumen conservado.

Para RNF-01 se mide desde descarga hasta comparación confirmada con el feed real completo. Para RNF-02 se registra aceptación/corte y efecto en el observador del simulador, con servicios sanos y sin cola previa; cada ensayo informa cantidad y frecuencia de cambios, lecturas y reintentos. No existe un cupo de deltas.

Para RNF-07 se observa durante veinticuatro horas, cada sesenta segundos y por separado: página y consulta autenticada en hasta cinco segundos; cambio pequeño en feed de control, ingesta por CLI y efecto externo en hasta sesenta segundos. La carga es controlada. Los disparos de sonda no cambian la programación de cinco horas, que se prueba por separado. Fallos, sondas faltantes, timeouts y reinicios propios cuentan como indisponibilidad. Las fallas externas se registran aparte. La campaña de cierres se realiza fuera de esa ventana.

Para RNF-09 se programan 9.000 consultas: cinco operadores durante treinta minutos, 50 % listados paginados de hasta cien vínculos, 25 % búsqueda de SKU y 25 % corridas/fallas. Se mide desde el cliente con motor activo, recursos declarados y sin ocultar errores. Las pruebas largas, la interfaz y ML son hitos del MVP, según el [roadmap](../roadmap/ROADMAP.md).
