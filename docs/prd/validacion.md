# Validación de proyecto — Ivo Stock

**Sincronización de inventario entre N fuentes de stock y K tiendas de MercadoLibre**


---

## Problema y actores

Un vendedor multi-tienda de MercadoLibre se abastece de varios proveedores (bodegas propias, distribuidores nacionales e importadores) y publica en varios países. Cada proveedor informa su stock en un formato propio: un CSV en un SFTP, un endpoint HTTP, una URL pública etc. Cada tienda de MercadoLibre expone su propia API autenticada por usuario.

Hoy esa conexión se resuelve con un script a medida **por cada par proveedor-tienda**, y ahí está el nudo del problema: para un seller multitienda y multipaís, integrar un proveedor una vez no alcanza — hay que **duplicar la misma integración de stock por cada tienda que da de alta**. El mismo feed, parseado igual, se lee y se mantiene N veces. El trabajo crece con el producto de proveedores por tiendas, no con la suma.

En el caso real que motiva el proyecto eso da **7 sistemas separados sosteniendo 2 fuentes de stock**: el costo de integrar no se amortiza, se repite. Sumar un proveedor o una vitrina significa escribir código nuevo, no cargar configuración.

La consecuencia de no sincronizar bien es concreta y medible: la misma unidad queda ofrecida en varias vitrinas a la vez, la primera venta deja sobrevendidas a las demás, y eso se paga en cancelaciones y reputación en MercadoLibre.

**Actores**

| Actor | Qué hace en el sistema |
|---|---|
| Responsable de catálogo | Conecta y desconecta proveedores y tiendas, con sus credenciales; revisa los vínculos SKU ↔ publicación propuestos, los aprueba o descarta, prende y apaga vínculos. |
| Responsable de publicaciones | Investiga fallas de actualización: publicaciones que dejan de aceptar stock, feeds que llegan corruptos, demoras de la API. |

## Solución a alto nivel

Una aplicación web que se configura, no se programa, para cada integración nueva.

**Alta de un proveedor (fuente de stock).** El sistema acepta **dos formatos y nada más**, y el alta empieza preguntando cuál es:

- **`.csv`** obtenido de un SFTP, un endpoint HTTP o una URL. El sistema pregunta el **separador**, si el archivo **tiene encabezado** y la **posición de la columna** de SKU y de stock (o su nombre, si hay encabezado).
- **Conexión a una tabla de PostgreSQL.** El sistema pide los datos de conexión, el nombre de la tabla y el **nombre de la columna** de stock y de SKU.

Durante el alta el sistema muestra un **preview best-effort** de las primeras filas ya parseadas, para que el usuario confirme que interpretó bien el formato antes de guardar. El alta no se da por buena hasta que **el sistema la valida con una prueba en vivo**: trae un puñado de SKU con su stock, los muestra al usuario y solo entonces el proveedor queda en estado *validado*. El usuario además le asigna una **prioridad (Baja / Media / Alta)**, que determina el peso que tendrán sus pedidos de actualización en la cola de trabajo. Con eso el sistema ingesta, normaliza y versiona el inventario de esa fuente sin escribir código específico.

**Alta de una tienda.** Flujo **OAuth 2.0** contra MercadoLibre: el usuario autoriza la aplicación y el sistema queda habilitado para leer su catálogo y escribir stock sobre sus publicaciones, con tokens renovables y revocables. Al completarse el alta arranca en background la **lectura del catálogo completo** de esa tienda, que deja en base los IDs de publicación y sus atributos. Si esa lectura falla no es catastrófico: se notifica y el sistema trabaja con el catálogo que alcanzó a traer. El usuario también puede **agregar catálogo a mano**: pega una lista de IDs, el sistema los busca en la API y se queda con los que existen. Desde ese momento el catálogo se mantiene actualizado por **webhooks de MercadoLibre**, que avisan la creación de publicaciones nuevas.

**Vinculación.** Se puede hacer en cualquier momento entre un proveedor *validado* y una tienda *autenticada*. Elegido el par, el sistema cruza los SKU de la fuente contra el catálogo de la tienda y **sugiere** las coincidencias. El responsable de catálogo acepta todas, algunas o ninguna, y puede buscar y excluir casos puntuales; lo que hoy descarta puede darlo de alta después, y al revés. Sobre vínculos existentes opera como un **interruptor ON/OFF**: el OFF envía la señal de stock cero a la tienda que participa de ese vínculo. Apagar un vínculo, dar de baja un proveedor y desconectar una tienda son el mismo hecho —una publicación se queda sin quien le escriba stock— y el sistema responde igual en los tres casos: **lleva la publicación a stock cero y recién después desactiva el vínculo**. Dejarla con su último valor conocido sería seguir ofreciendo unidades que ya nadie respalda.

**Motor de sincronización.** Son dos procesos separados, acoplados solo por el estado. La **ingesta** termina actualizando el *estado vigente* del proveedor (SKU → stock) y no escribe en ninguna tienda. Cada corrida **reemplaza** ese estado completo: un SKU que el proveedor deja de informar vale cero, igual que si viniera con cero explícito, porque un SKU que la fuente ya no lista es un SKU que ya no puede respaldar. Cada actualización de ese estado notifica a un **worker comparador**, que contrasta el stock de los vínculos de ese proveedor contra el estado vigente y encola una tarea **solo por cada diferencia**, **con la prioridad heredada del proveedor**, que define su posición frente a las demás. Encolar es **idempotente por vínculo**: la cola admite a lo sumo una tarea pendiente por vínculo y una tarea nueva reemplaza a la anterior, de modo que el trabajo acumulado es proporcional a la cantidad de vínculos desactualizados y no a la cantidad de corridas atrasadas. La publicación respeta los límites de consumo por tienda —**60 req/min**, compartidos entre escritura de stock y lectura de catálogo— y reintenta ante errores transitorios. Si la API de MercadoLibre devuelve un **error no reintentable** (publicación inexistente o cerrada, token revocado, payload rechazado), la actualización no se descarta en silencio: se guarda como **dead letter** en una tabla aparte, con el delta, la respuesta de la API y el momento de la falla, y queda **revisable desde el tablero de salud** para que el responsable de publicaciones la analice y decida. Cada actualización, exitosa o no, queda auditada: qué SKU, qué publicación, qué valor anterior, qué valor nuevo, qué respondió la API.

**Componentes**

1. **Frontend web** — altas; revisión de vínculos; tablero de salud de feeds y vínculos; vista de tiendas (tiendas conectadas, su estado, vínculos por tienda); vista de proveedores (alta, modificación y baja).
2. **API core** — autenticación de usuarios, configuración, OAuth de tiendas, vínculos.
3. **Worker de ingesta** — descarga, normalización y validación de feeds heterogéneos; deja actualizado el estado vigente del proveedor.
4. **Worker comparador** — notificado ante cada cambio del estado vigente, compara contra el stock de los vínculos afectados y encola las diferencias. Es también el que responde a los otros disparadores: alta de un vínculo, encendido y apagado, baja de un proveedor y desconexión de una tienda.
5. **Worker de publicación** — consumo de la cola por prioridad y escritura contra la API de MercadoLibre, con control de rate limit.
6. **Worker de catálogo** — lectura inicial del catálogo de una tienda nueva, recepción de los webhooks de las tiendas autenticadas con las publicaciones nuevas, y validación de los IDs que el usuario carga a mano (los que existen y no estaban en base, los incorpora).

**Requisitos base que cubre:** patrón arquitectónico explícito (servicios con cola de eventos entre ingesta y publicación), modelo de datos documentado, CI/CD, readiness cloud, RF y RNF de producción (latencia de propagación, tasa de error por tienda, control de acceso, manejo de credenciales).

**Áreas que incorpora de manera sustantiva:**

- **Ingeniería de datos:** pipeline de ingesta y transformación sobre feeds reales heterogéneos y sucios (encodings distintos, SKU como texto o entero, duplicados, filas vacías, columnas que cambian de nombre).
- **Calidad, trazabilidad y gobernanza:** validación por feed, cuarentena de corridas anómalas (por ejemplo, una caída abrupta del stock total sugiere feed truncado, no venta masiva), y auditoría completa de cada escritura al marketplace.
- **Combinación de motores de almacenamiento, cada uno por una necesidad real:** PostgreSQL (usuarios, proveedores, tiendas, vínculos, estado vigente de stock), object storage compatible con S3 (snapshot crudo e inmutable de cada feed ingestado, para trazabilidad y replay), y Redis (cola de deltas con prioridad y control de rate limit por tienda), con persistencia y réplica para que una caída con la cola cargada no pierda trabajo pendiente.
- **Procesamiento por eventos:** la cola de deltas es el mecanismo de integración entre ingesta y publicación, no un detalle de implementación.
- **Observabilidad y operación:** logging estructurado, métricas por feed y por tienda, health checks, y un tablero de vínculos en falla.

## Fuentes de datos identificadas y verificadas

**1. Feed de stock de Celesa (proveedor real, en producción hoy).**
Endpoint HTTP con autenticación por parámetros de query, ya consumido por el sistema legacy de la empresa:

```
http://www.azetadistribuciones.es/servicios_web/stock.php?fr_usuario=<usuario>&fr_clave=<clave>
```

**Volumen:** ~650.000 SKU. **Frecuencia de actualización:** cada 30 minutos. **Acceso:** credenciales propias de la empresa, disponibles para el equipo. **Formato:** texto plano, una línea por SKU, campos separados por `;` — `SKU;stock` — **sin encabezado**, y con filas cuyo valor de stock no es numérico y hay que descartar.

En el contrato de alta se configura como un `.csv` con separador `;`, sin encabezado, SKU en la primera posición y stock en la segunda. Y es justamente el caso que obliga a una decisión de diseño real: el alta no puede pedir solo *nombre de columna*, porque hay fuentes sin encabezado; tiene que aceptar también **separador y posición de campo**. Es el tipo de heterogeneidad que justifica el proyecto.

**Otras fuentes ya relevadas, para dimensionar el diseño** (no todas entran al MVP): Ingram ~10 millones de SKU, SBS ~1 millón, bodegas propias ~50 mil. Sirven para fijar el orden de magnitud del motor de sincronización y para justificar que la propagación se haga por deltas y no por reescritura completa.

**2. API de MercadoLibre (contrato real, acceso público documentado).**
Catálogo de publicaciones propias y escritura de stock. **Acceso:** aplicación registrada gratis en el portal de desarrolladores, autenticación **OAuth 2.0** (authorization code + refresh token). **Frecuencia:** consulta bajo demanda, con límites de llamadas por aplicación y por usuario que el sistema debe respetar explícitamente. **Volumen relevante:** miles de publicaciones por vitrina; el diseño apunta a soportar vínculos en el orden de las decenas de miles sin degradar la latencia de propagación. **Licencia:** términos de uso de la plataforma; sin costo.

**3. Tiendas de MercadoLibre simuladas (datos sintéticos, generador propio, parte del sistema).**
El lado del marketplace **se simula**, y esto es una decisión explícita, no un plan de contingencia: escribir stock sobre publicaciones productivas reales es una operación con consecuencias comerciales, y depender de credenciales de una empresa privada haría que el TP no se pueda corregir localmente. El sistema incluye entonces un **MercadoLibre simulado** que implementa el mismo contrato que el real: el **flujo OAuth 2.0 completo** (authorization code, refresh, revocación), los endpoints de catálogo y de actualización de stock, los **webhooks** de publicación nueva, los **límites de llamadas** y los errores reintentables y no reintentables.

Ese simulador viene con un **generador de catálogo sintético**: publicaciones con ID, atributos y SKU, donde los SKU se muestrean del **feed real de Celesa** para que el matching de vinculación se ejercite contra datos verdaderos de un lado y sintéticos del otro. El generador es configurable (cantidad de tiendas, publicaciones por tienda, proporción de SKU coincidentes, publicaciones muertas que rechazan actualizaciones, latencia y tasa de error de la API) y **queda en el repositorio como componente del sistema**, versionado y testeado. Es lo que permite provocar a demanda los escenarios que la API real no produce cuando uno los necesita: rate limit alcanzado, token revocado a mitad de una corrida, publicación cerrada.

Los workers escriben siempre contra una **interfaz de marketplace**, con dos implementaciones detrás —la simulada y la real— de modo que conectar una tienda productiva más adelante es cambiar configuración, no reescribir el motor.

## Viabilidad preliminar

Es realizable por 3 personas porque el alcance está deliberadamente acotado a un ciclo corto y repetido: *leer un feed, calcular un delta, escribirlo en una o varias publicaciónes, auditarlo*. La complejidad está en la ingeniería: heterogeneidad de las fuentes, idempotencia, límites de consumo, observabilidad etc. Además uno de los integrantes conoce el dominio y ya tiene los datos y las credenciales, lo que elimina la etapa de relevamiento.

**Mayor riesgo técnico: el motor de sincronización contra la API de MercadoLibre.** Concentra tres problemas a la vez: límites de llamadas que obligan a priorizar deltas en lugar de reescribir todo, idempotencia (una corrida repetida no puede duplicar efectos), y manejo del ciclo de vida de los tokens OAuth de K tiendas. Es el riesgo que la Entrega 2 tiene que dejar resuelto: el POC apunta a una ruta completa —el feed real de Celesa, una tienda contra el contrato real de MercadoLibre, stock propagándose de punta a punta con auditoría— antes de generalizar a N×K.

**Riesgo secundario: calidad de los feeds.** Un CSV truncado propagado sin validación pone en cero el stock de miles de publicaciones. Se mitiga con validación y cuarentena por corrida, que además es parte del contenido de gobernanza de datos que el TP pide.

**Plan B: el sistema reconoce su propio estado degradado y se detiene en lugar de propagar basura.** No es un plan B de reemplazo de datos, es una propiedad del sistema:

- **Si falla el acceso a la API de MercadoLibre** —caída, tokens revocados, o una tarea de actualización encolada hace más de **12 horas**— el sistema marca la tienda afectada como *degradada*, deja de consumir la cola para ella y **alerta al usuario** para que continúe el trabajo pendiente desde el frontend de MercadoLibre. La cola queda persistida y se reanuda cuando el servicio vuelve.
- **Si falla el acceso al feed de un proveedor**, o si la validación detecta corrupción severa en una corrida (feed truncado, caída abrupta del stock total, mayoría de filas no parseables), la corrida queda en cuarentena, **no se propaga ningún delta** y el proveedor pasa a *degradado* con alerta. El sistema se queda en standby sobre esa fuente y sigue operando normalmente con las demás.

Nada de esto bloquea la construcción ni la corrección del TP: el estado degradado es parte del alcance y se demuestra provocándolo, usando el simulador de MercadoLibre descrito en *Fuentes de datos* para forzar caídas, rate limit y tokens revocados. Del lado del proveedor se trabaja con el feed real de Celesa, y el generador sintético de feeds (separador, encabezado, filas corruptas, deriva de stock) cubre los formatos y las fallas que Celesa no produce a demanda.

## Alcance del MVP

**Adentro**

- Registro y login de usuarios; control de acceso sobre las operaciones de configuración.
- Alta de proveedores con dos formatos soportados: `.csv` (SFTP / endpoint / URL, con separador, encabezado sí/no y posición de campo) o tabla de PostgreSQL (con nombre de columna), más **preview best-effort**, **validación del alta con un fetch de prueba** y **prioridad Baja / Media / Alta**.
- Alta de tiendas de MercadoLibre por flujo OAuth 2.0, con almacenamiento seguro y renovación de tokens.
- Lectura en background del catálogo completo de cada tienda nueva, carga manual de IDs con validación contra la API, y mantenimiento del catálogo por webhooks de publicaciones nuevas.
- Ingesta programada y re-ejecutable de feeds, con snapshot crudo, normalización y validación por corrida.
- Vinculación en cualquier momento entre proveedor validado y tienda autenticada, con matching sugerido por SKU y aprobación, búsqueda y exclusión manual.
- Vínculo como interruptor ON/OFF: el OFF propaga stock cero a la tienda de ese vínculo. La baja de un proveedor y la desconexión de una tienda disparan la misma acción sobre los vínculos alcanzados.
- Motor de deltas y publicación de stock contra la API, con **cola por prioridad**, reintentos, respeto de límites de consumo, idempotencia y **cola de dead letters** para los errores no reintentables.
- Auditoría de toda escritura y tablero de salud: feeds, vínculos en falla, dead letters revisables, latencia de propagación, y **estado degradado con alerta** por tienda y por proveedor.
- **Simulador de MercadoLibre** (OAuth 2.0, catálogo, actualización de stock, webhooks, rate limit y errores) con su **generador de catálogo sintético**, detrás de la misma interfaz de marketplace que usaría la API real.
- Levantamiento local completo con `docker-compose`, CI con build y tests, ADRs de las decisiones estructurales.

**Explícitamente afuera**

- **Gestión de ventas, reservas, despacho y logística** — es el resto del sistema real; este TP es solo inventario.
- **Pricing** — el sistema nunca lee ni escribe precios.
- **Creación de publicaciones** — el sistema asume que la publicación existe; no la crea ni la repara.
- **Reparación de publicaciones muertas** — el sistema detecta y alerta que una publicación dejó de aceptar actualizaciones; qué hacer con ella es decisión humana fuera del sistema.
- **Compensar lo que la fuente no ofrece** — si un feed no expone algo, el sistema no lo emula.
- **Gestión de inventario a nivel bodega** (ubicaciones, movimientos, conteos) y **reportería de negocio**.
- **Reparto o topeo de stock entre vitrinas** — si la fuente informa 10 unidades, las K vitrinas ven 10.
- **Ingesta por streaming** — las fuentes son archivos y endpoints con frecuencia horaria; la ingesta es batch y re-ejecutable, y el mecanismo de eventos es interno (cola de deltas).

## Pendiente de definir

El componente de **Machine Learning** que exige la Entrega 3 todavía no está decidido y se define antes de la Entrega 1. Los candidatos naturales dentro de este alcance son la **detección de anomalías en feeds de stock** (clasificar una corrida como confiable o sospechosa antes de propagarla, que hoy es un umbral fijo) y la **predicción de quiebre de stock por SKU**. Ambos se apoyan en datos que el sistema ya genera por diseño —el histórico de snapshots crudos y la auditoría de actualizaciones— y no requieren fuentes adicionales.
