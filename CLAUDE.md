# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Es un **documento vivo**: actualizalo cuando se tomen decisiones. Debe mantenerse consistente con `docs/prd/validacion.md`, `docs/prd/PRD.md`, el README, los ADRs y el SRD. Si algo acá contradice una instrucción del usuario en la sesión, **gana el usuario** — y después se actualiza este archivo.

## Qué estamos construyendo

**Ivo Stock** — sincronización de inventario entre **N fuentes de stock** y **K tiendas de MercadoLibre** (TP Integrador, Ingeniería de Software, UdeSA, Primavera 2026).

Una aplicación web que **se configura, no se programa**, para cada integración nueva. El usuario da de alta proveedores (un `.csv` en un SFTP / endpoint / URL, o una tabla de PostgreSQL, identificando las columnas de SKU y de stock), da de alta tiendas por **flujo OAuth 2.0** contra MercadoLibre, vincula SKU con publicaciones, y el sistema mantiene el stock sincronizado propagando **deltas** con auditoría completa.

El problema real que ataca: hoy cada par proveedor-tienda se resuelve con un script a medida, así que el trabajo de integrar crece con el **producto** de proveedores por tiendas y no con la suma. En el caso que motiva el proyecto eso da **7 sistemas separados sosteniendo 2 fuentes de stock**. La consecuencia de no sincronizar bien es sobreventa: cancelaciones y reputación.

TP grupal (2-3 personas) que simula un sistema de software real en producción, integrando software + datos + ML. Se evalúa criterio de ingeniería, no originalidad.

**Este proyecto es un pivot.** Es una versión simplificada y acotada al pilar de **inventario** de un sistema real más grande (`ivo-monopoly`), que también cubre ventas, reservas y despacho. Nada de eso entra acá. El proyecto anterior del TP (asistente 3D de amoblamiento con Amazon Berkeley Objects) está **abandonado**; sus documentos quedaron en `docs/basura-vieja/`. 

**Proyecto padre.** El PRD del padre vive en `C:\ivo-monopoly\docs\PRDs\sin-terminar\PRD00.md` y es la fuente de verdad del dominio: leelo antes de inventar semántica. Tres cosas que se heredan y no se discuten acá:

- **Vocabulario:** lo que el padre llama **bodega** acá es **proveedor**, y lo que llama **vitrina** acá es **tienda**. `vínculo`, `MLX`, `SKU` (= ISBN) y `publicación muerta` se usan igual. El **Buyer** y la **ruta bodega–vitrina** no existen en este alcance.
- **Invariantes** (en el PRD se llaman **INV-1/2/3**; en el PRD00 son R1, R3 y R8): **INV-1** una publicación tiene un único vínculo activo que le escribe stock; **INV-2** el stock se ofrece completo en las K tiendas, sin repartir ni topear, y la sobreventa resultante es un riesgo aceptado a nivel producto; **INV-3** un proveedor caído se degrada a stock cero de forma paulatina, nunca bloqueando el pipeline.
- **Divergencias deliberadas:** sin publicaciones compartidas, sin roles, solo dos formatos de origen, y 10⁵ vínculos demostrados contra los 10⁸ que exige el original. **El PRD no nombra a Ivo Monopoly**: lo llama "el sistema original" y no entra en su vocabulario interno (bodega, vitrina, Buyer, ruta). Mantené ese criterio al editarlo.
## Estado actual del repositorio

Etapa de **validación de proyecto** (pre-Entrega 1). Verificado al 2026-09-18:

- **No hay código.** El repo contiene solo documentación.
- **No hay `.git` inicializado en este directorio**, pese a que la consigna exige repositorio privado, compartido con la cátedra desde el inicio, con historia que refleje la contribución real de cada integrante. Inicializar el repo es prerrequisito, no un detalle — y a esta altura bloquea la entrega, no el desarrollo.
- `docs/prd/validacion.md` — documento de validación de proyecto (el de 1-2 carillas que pide la cátedra). **Documento padre**: si algo lo contradice, hay un error que corregir en uno de los dos.
- `docs/prd/PRD.md` — PRD tentativo (versión 00): relación con el proyecto padre y vocabulario equivalente, casos de uso CU-01…CU-09, requisitos funcionales RF-01…RF-48 con MoSCoW y asignados a POC o MVP (**no existe RF-02**, ver la nota del propio PRD), RNF-01…RNF-16 con objetivo verificable, criterios de éxito, supuestos S-01…S-08, limitaciones, riesgos R-01…R-05 con ROAM, roadmap y glosario.
- `docs/prd/obs.md` — observaciones del usuario sobre la validación.
- `docs/consignas/consigna-completa.md` — enunciado oficial del TP.
- `docs/consignas/consigna-resumida.md` — versión condensada; usar esta para consultas rápidas.
- `docs/basura-vieja/` — documentación del proyecto abandonado. **No usar como fuente.**
- `sessions/` — bitácoras de sesiones (ver `~/.claude/CLAUDE.md`).

No asumas que hay un stack corriendo hasta que la sección "Comandos" lo confirme.

## Entregas

1. **Entrega 1 — Diseño:** PRD (perspectiva del usuario: problema, usuarios y casos de uso, RF priorizados, RNF, criterios de éxito medibles, supuestos y limitaciones) + fuentes de datos y viabilidad profundizadas + Roadmap a POC y MVP. Requiere proyecto ya aprobado.
2. **Entrega 2 — POC + SRD:** flujo principal de punta a punta con datos reales, alcance reducido, **el riesgo técnico más grande ya resuelto**. CI y testing operativos. Levantable localmente. ADRs. SRD sin componentes de ML todavía.
3. **Entrega 3 — MVP:** todos los RF imprescindibles funcionando, ciclo de vida automatizado, readiness cloud demostrable, RNF verificables incluyendo observabilidad, pipeline de ML reproducible con serving y monitoreo, SRD completo.


Cada entrega: link a un commit en `main` + README actualizado + directorio de ADRs + video de 5-12 minutos. Lo que no esté integrado a `main` al momento de la entrega **no se corrige**; lo que no se pueda verificar por código y no esté demostrado en el video se considera no hecho.

## Reglas duras (no negociables)

- **El sistema debe levantarse localmente con un procedimiento simple y documentado.** Es el mecanismo principal de corrección de la materia, exista o no un deploy vivo. Priorizá `docker-compose` o un único target (`make up`) que levante todo, **incluido el simulador de MercadoLibre**, sin credenciales externas. Mantené las instrucciones del README al día.
- **Patrón arquitectónico explícito y justificado.** La coherencia entre el patrón declarado y lo efectivamente construido es criterio de evaluación directo.
- **Sin costos significativos.** Free tiers, recursos efímeros o ejecución local. No introduzcas servicios cloud pagos siempre-encendidos.
- **Secretos por variables de entorno / `.env` (gitigneado). Nunca commitees credenciales, tokens ni claves.** Crítico acá: el proyecto maneja credenciales de proveedores reales y tokens OAuth de cuentas reales. En documentación, las URLs con credenciales van con placeholders (`<usuario>`, `<clave>`).
- **No commitear datos.** Snapshots de feeds, catálogos generados y volcados de stock NO van al control de versiones. El repo se mantiene liviano; los datos se obtienen o se generan con scripts del propio sistema.
- **Nunca escribir stock contra publicaciones productivas reales.** El desarrollo y la demo van contra el simulador. Una escritura equivocada tiene consecuencias comerciales para una empresa real.
- **Cada decisión estructural lleva un ADR que COMPARA ALTERNATIVAS.** Un ADR que solo describe el camino elegido es inválido para la evaluación. Formato simple: contexto, opciones consideradas con sus trade-offs, decisión, consecuencias.
- **CI/CD y testing operativos desde la Entrega 2** (POC), no recién en el MVP. Los **caminos de falla** (cuarentena, dead letter, rate limit, token revocado) llevan test propio.
- **Honestidad en resultados.** Nada de outputs fabricados para la demo; lo que se muestra tiene que ser reproducible desde el código. Que el marketplace esté simulado se declara, no se disimula.
- **Datos reales** (públicos, propios o sintéticos). Si son sintéticos, **el generador es parte del sistema y se evalúa como tal** — por eso los generadores y el simulador son RF (RF-35 a RF-38), no herramientas de testing.
- **Commits chicos y coherentes, con mensajes claros.** La materia evalúa la historia de git y la contribución real de cada integrante, sin excepción.
- **Todo lo declarado debe ser verificable en el repo.** Validación, PRD, SRD, ADRs y código tienen que contar la misma historia.

## Producto — flujos

**Alta de un proveedor (fuente de stock).** El sistema acepta **dos formatos y nada más**, y el alta empieza preguntando cuál es:

- **`.csv`** desde SFTP, endpoint HTTP o URL. Pregunta el **separador**, si **tiene encabezado**, y la **posición** de la columna de SKU y de stock (o su nombre, si hay encabezado). La posición es obligatoria porque hay fuentes reales sin encabezado — pedir solo "nombre de columna" no alcanza.
- **Conexión a una tabla de PostgreSQL.** Pide los datos de conexión, el nombre de la tabla y el **nombre de columna** de SKU y de stock.

Después muestra un **preview best-effort** de las primeras filas ya parseadas, y el alta no se da por buena hasta que **el sistema la valida con un fetch de prueba** (unos pocos SKU con su stock). Solo entonces el proveedor queda *validado*. El usuario le asigna una **prioridad (Baja / Media / Alta)**, que heredan sus deltas y define su posición en la cola de trabajo.

**Alta de una tienda.** Flujo **OAuth 2.0** (authorization code + refresh + revocación) contra MercadoLibre. Al completarse arranca en background la lectura del catálogo, **en dos etapas**: primero los identificadores MLX de la tienda y, con la lista completa, el stock y los atributos de cada publicación. Ese stock leído es el que después evita escrituras al vano. Si la lectura falla no es catastrófico: se notifica y se trabaja con lo que se alcanzó a traer. El usuario puede **cargar IDs a mano** (se validan contra la API y se incorporan los que existen). Desde ahí el catálogo se mantiene por **webhooks** de publicación nueva.

**Vinculación.** En cualquier momento entre un proveedor *validado* y una tienda *autenticada*. El sistema cruza SKU contra catálogo y **sugiere** coincidencias; el usuario acepta todas, algunas o ninguna, con búsqueda y exclusión puntual. Sobre vínculos existentes opera como **interruptor ON/OFF**: el OFF propaga **stock cero** a la tienda de ese vínculo, y apagarlo **conserva su historia** (no es un alta y una baja). **Regla única de corte (RF-47):** apagar un vínculo, dar de baja un proveedor y desconectar una tienda disparan la misma acción — cero primero, desactivación después. Nunca dejes una publicación con el último stock conocido de una fuente que dejó de alimentarla. **Sin reparto ni topeo**: si la fuente informa 10 unidades, las K tiendas ven 10. **Una publicación admite un único vínculo activo**: el segundo intento se rechaza con error.

Dos reglas que ordenan el arranque y son fáciles de romper al implementar: **vincular exige al menos una corrida aceptada** del proveedor (la lista de SKU sale de ahí, no del fetch de prueba del alta), y **al crear un vínculo se compara el stock del proveedor contra el que MercadoLibre reporta para esa publicación, encolando solo las diferencias**. De ahí se deduce que la primera corrida de un proveedor nunca propaga nada: todavía no hay vínculos.

**Motor de sincronización.** Snapshot crudo → normalización → **estado vigente** → comparación contra los vínculos → **delta**. Solo los deltas se propagan. Cada corrida aceptada **reemplaza** el estado vigente completo: **un SKU que no viene en la corrida vale cero**, igual que un cero explícito, y no conserva su valor previo. Cada delta entra a la cola con la prioridad del proveedor; **el encolado es idempotente por vínculo** (RF-46): a lo sumo una tarea pendiente por vínculo, y la nueva reemplaza a la pendiente conservando su prioridad. La publicación respeta los límites de consumo por tienda, es **idempotente** y reintenta con backoff ante errores transitorios. Un **error no reintentable** (publicación cerrada, token revocado, payload rechazado) no se descarta en silencio: va a **dead letter** con el delta, la respuesta de la API y el momento de la falla, revisable desde el tablero de salud. Toda escritura queda auditada.

**Degradación explícita (el "plan B" es una propiedad del sistema, no un reemplazo de datos).** Ante falla de una tienda —caída, token revocado, o una tarea de actualización **encolada hace más de 12 horas**— la tienda pasa a *degradada*, se deja de consumir la cola para ella y se **alerta al usuario** para que continúe desde el frontend de MercadoLibre; la cola persiste y se reanuda. Ante falla o corrupción severa de un feed, la corrida queda en **cuarentena**, **no se propaga ningún delta**, el proveedor pasa a *degradado* y las demás fuentes siguen operando.

La corrupción de una corrida se decide con el **coeficiente de sospecha** definido en CU-07 del PRD: cuarentena si `p > 0.5`, con `p = 1 − (1−d)(1−z)` sobre dos señales, SKU faltantes (`D`, tolerancia `0.10`) y ceros nuevos en masa (`Z`, tolerancia `0.25`). Las tolerancias se calibran contra el histórico real de Celesa — el criterio es que ninguna corrida normal caiga en cuarentena y que un feed truncado sí.

**Los errores de parseo no entran al coeficiente**: un stock de texto o negativo descarta la fila; un stock **en blanco se interpreta como sin stock (0)**, no como dato ausente, así que el SKU no conserva su valor vigente. Pasado el **10 % de filas con error de parseo** se emite una alerta que **no** detiene la corrida — el umbral es fijo, no se calibra. No hace falta que la detenga: una fila descartada es un SKU ausente (lo mide `D`) y una columna de stock vacía es un cero (lo mide `Z`). Celesa trae filas de stock no numérico en operación normal, y por eso la tasa de parseo es diagnóstico y no guarda.

## Fuentes de datos

**1. Feed de stock de Celesa (proveedor real, en producción hoy).** Endpoint HTTP con autenticación por parámetros de query, credenciales propias de la empresa. ~**650.000 SKU**, actualización cada **30 minutos**, texto plano `SKU;stock` separado por `;`, **sin encabezado**, con filas de stock no numérico a descartar. Es la fuente real del lado proveedor y el caso que justifica el contrato de alta por separador + posición.

Otras fuentes relevadas, solo para dimensionar (no entran al MVP): Ingram ~10M SKU, SBS ~1M, bodegas propias ~50k. Sirven para justificar propagación por deltas en lugar de reescritura completa.

**2. API de MercadoLibre (contrato real, público y documentado).** Aplicación registrada gratis, OAuth 2.0, catálogo y escritura de stock, webhooks, límites de llamadas por aplicación y por usuario. Sin costo.

**3. Tiendas de MercadoLibre simuladas (sintéticas, generador propio, parte del sistema).** **Decisión explícita, no contingencia.** Incluye:

- **Simulador de MercadoLibre** que implementa el contrato real: OAuth 2.0 completo, catálogo, actualización de stock, webhooks, rate limits, y errores reintentables y no reintentables.
- **Generador de catálogo sintético** configurable (tiendas, publicaciones por tienda, proporción de SKU coincidentes, publicaciones muertas, latencia, tasa de error), con **SKU muestreados del feed real de Celesa** para que el matching se ejercite contra datos verdaderos de un lado.
- **Generador de feeds sintéticos** (volumen, separador, encabezado, filas corruptas, deriva de stock), para los formatos y fallas que Celesa no produce a demanda.

Es lo que permite provocar rate limit, token revocado a mitad de corrida y publicación cerrada cuando hacen falta.

## ML — PENDIENTE DE DEFINIR (no construir nada todavía)

La Entrega 3 exige un pipeline de ML reproducible con serving y monitoreo. El candidato es la **detección de anomalías en corridas de feed** —clasificar una corrida como confiable o sospechosa antes de propagarla—, alimentada por datos que el sistema ya genera (histórico de snapshots crudos + auditoría de actualizaciones), sin fuentes adicionales.

El enganche está definido: el MVP decide con el **coeficiente de sospecha de CU-07** (señales `D` faltantes y `Z` ceros nuevos, combinadas con *noisy-OR* contra tolerancias fijas). El modelo reemplaza esas tolerancias por **pesos aprendidos sobre corridas etiquetadas**, con las mismas señales y el mismo umbral. Hasta entonces el coeficiente es un *score*, no una probabilidad calibrada: no lo documentes como probabilidad.

Se confirma antes de cerrar la Entrega 1 y **se registra con un ADR**. No armes pipeline de ML de forma especulativa.

## Arquitectura (bosquejo, en evolución)

Patrón declarado: **servicios con cola de eventos**. La cola de tareas de actualización —entre el comparador y la publicación— es el mecanismo de integración, no un detalle de implementación.

1. **Frontend web** — altas de proveedores y tiendas; revisión de vínculos; tablero de salud (feeds, vínculos en falla, dead letters, latencia); vista de tiendas; vista de proveedores.
2. **API core** — autenticación, configuración, OAuth de tiendas, vínculos. **Sin roles ni permisos diferenciados**: los dos perfiles del PRD (responsable de catálogo y responsable de publicaciones) son responsabilidades organizativas, no roles del sistema. Todo usuario autenticado puede operar cualquier configuración; lo que se exige es que ningún endpoint responda sin sesión.
3. **Worker de ingesta** — descarga, normalización, snapshot crudo y validación de corrida. Su único producto es el **estado vigente** del proveedor; no escribe en ninguna tienda.
4. **Worker comparador** — notificado ante cada cambio del estado vigente, compara contra el stock de los vínculos afectados y encola **solo las diferencias**. Atiende también los otros disparadores: alta de vínculo, ON/OFF, baja de proveedor, desconexión de tienda, tienda que sale de degradada.
5. **Worker de publicación** — consume la cola por prioridad y escribe contra la API, con rate limit, reintentos, idempotencia y dead letters.
6. **Worker de catálogo** — lectura inicial del catálogo de una tienda nueva (MLX primero, después stock y atributos), recepción de webhooks, validación de los IDs cargados a mano.

**No fusiones ingesta y comparación en un solo worker.** Son dos procesos separados acoplados solo por el estado vigente: la ingesta no sabe de vínculos, y la comparación tiene disparadores que no son feeds. La cola entre el comparador y la publicación es la pieza que tiene que ser **robusta y resistente a fallas** — tareas persistidas, entrega al menos una vez, apoyada en idempotencia, y **a lo sumo una tarea pendiente por vínculo** (la nueva reemplaza a la vieja). Esa última propiedad acota la cola pendiente de una tienda a su cantidad de vínculos activos, sin importar cuántas corridas se acumulen.

Los workers escriben **siempre contra una interfaz de marketplace única**, con dos implementaciones detrás (simulada y real) seleccionables por configuración. Conectar una tienda productiva más adelante es cambiar configuración, no reescribir el motor.

**Cota dura que ordena todo el diseño:** la API de MercadoLibre permite **60 req/min por tienda** (documentación oficial), o sea **3.600 actualizaciones por hora y por tienda**. Ninguna decisión de infraestructura propia la mueve, y **el presupuesto es compartido entre escribir stock y leer catálogo** (webhooks, validación de IDs a mano, relecturas manuales): todas las llamadas a una tienda pasan por el mismo control de cuota. La única lectura que no compite es la inicial de una tienda nueva, porque en ese momento esa tienda todavía no tiene vínculos.

De esa cota salen los objetivos de latencia de RNF-01, y no al revés: 3.600 por hora son **21.600 en 6 horas** (p95) y **43.200 en 12** (p100, y superarlo declara la tienda degradada). No propongas objetivos de minutos: medirían el tamaño de la corrida, no la calidad de la implementación. Una corrida que genere más diferencias que eso deja cola acumulada, y ahí la prioridad por proveedor decide qué se actualiza primero. **El simulador implementa el mismo límite** — no lo configures con valores cómodos, porque entonces el POC no ejercita el caso que importa.

**Storage (variedad justificada por necesidad real):**
- **PostgreSQL** — usuarios, proveedores, tiendas, vínculos, estado vigente de stock, auditoría, dead letters.
- **Object storage compatible con S3** (MinIO en local) — snapshot crudo e **inmutable** de cada corrida, para trazabilidad y replay.
- **Redis** — cola de deltas con prioridad y control de rate limit por tienda, con persistencia y réplica.

*Matiz de diseño que vale un ADR:* la cola es **reconstruible** (delta = estado vigente − último snapshot), así que la réplica de Redis compra **disponibilidad, no durabilidad**. Decidir "cola en memoria reconstruible vs. cola durable en Postgres" con ese argumento explícito, no por default.

**ADRs candidatos:** monolito modular vs. servicios separados; cola en Redis reconstruible vs. cola durable en Postgres; simulador propio vs. mocks o grabaciones de la API real; snapshots en object storage vs. en Postgres; lenguaje/framework de la API core y de los workers; estrategia de cálculo de deltas (diff completo vs. incremental).

## Stack (PROPUESTO — confirmar y registrar en ADR)

Provisional; no lo trates como cerrado.

- **Frontend:** aplicación web; framework a confirmar (la interfaz es de formularios y tablas, no hay requerimiento gráfico).
- **API core y workers:** a decidir por ADR (Python/FastAPI o Node son los candidatos razonables; el dominio es ingesta de datos y clientes HTTP).
- **PostgreSQL** · **object storage compatible S3 (MinIO en local)** · **Redis**.
- **Orquestación local:** Docker Compose.
- **Simulador de MercadoLibre:** servicio propio en el mismo compose.

## Convenciones del repositorio

- **README** siempre con instrucciones actualizadas para levantar todos los componentes localmente.
- **`/adr`** (o `/docs/adr`): un archivo por decisión, formato compara-alternativas.
- **Observabilidad de primera clase, no un agregado:** logging estructurado con **identificador de corrida trazable de punta a punta**, métricas por feed y por tienda, health checks por componente. Para el modelo (cuando exista), monitorear **salud del pipeline y distribución de predicciones**.
- **Testing** desde el POC; que el CI corra build + tests, **incluidos los caminos de falla**.
- **Config por entorno**; nada hardcodeado ni secreto en el código.
- **Manejo de errores** explícito en las interfaces expuestas; control de acceso en los endpoints.
- **Partes mockeadas o simplificadas** están permitidas y esperadas en el POC, pero deben quedar identificadas en el README.
- **Nomenclatura de requisitos:** referí siempre por ID (`RF-22`, `RNF-03`, `CU-04`, `S-02`) para que código, SRD y PRD sean rastreables entre sí.

## Comandos

Pendiente — completar cuando exista el repo. Placeholder:

```
# make up          # levantar todo localmente (incluye el simulador)
# make test        # correr tests
# make ingest      # ejecutar una corrida de ingesta
# make gen-catalog # generar catálogo sintético para el simulador
# make gen-feed    # generar un feed sintético
```

## Cómo trabajar acá

- Al proponer stack, arquitectura o herramientas, chequear la decisión contra las reglas duras (costo, levantable local, readiness cloud, repo liviano, cero credenciales) antes de sugerirla.
- Al tomar una decisión estructural, escribir el ADR correspondiente en el mismo cambio, con alternativas comparadas.
- Mantener actualizadas la sección "Comandos" de este archivo y el README a medida que aparezca código.
- Los `.md` de `docs/prd/` son la fuente de verdad del alcance. Si el código se aparta, se corrige el código o se corrige el documento — pero no quedan en contradicción.

## Explícitamente fuera de alcance / rechazado

- **Gestión de ventas, reservas, despacho y logística** — es el resto del sistema real (`ivo-monopoly`); este TP es solo inventario.
- **Pricing** — el sistema nunca lee ni escribe precios.
- **Creación de publicaciones** — se asume que la publicación existe; el sistema no la crea.
- **Reparación de publicaciones muertas** — el sistema detecta y alerta; qué hacer es decisión humana, fuera del sistema.
- **Reparto o topeo de stock entre tiendas.**
- **Gestión de inventario a nivel bodega** (ubicaciones, movimientos, conteos) y **reportería de negocio**.
- **Compensar lo que la fuente no ofrece** — si el feed no lo expone, el sistema no lo emula.
- **Formatos de origen más allá de `.csv` y tabla PostgreSQL** — el contrato es deliberadamente cerrado. No agregues XML, JSON ni Excel sin decisión explícita (el padre acepta Excel por FTP; acá no).
- **Publicaciones compartidas** — un MLX alimentado por varios proveedores a la vez, con stock por depósito. Existe en el padre, acá no: una publicación, un vínculo activo.
- **Ingesta por streaming** — las fuentes son archivos y endpoints con frecuencia de minutos u horas; la ingesta es batch y re-ejecutable, y el mecanismo de eventos es interno (cola de deltas).
- **El proyecto anterior (asistente 3D de amoblamiento, Amazon Berkeley Objects, CLIP/KNN, canvas 3D)** — abandonado. No lo retomes ni lo cites como contexto vigente.

## Limitaciones conocidas (ser honesto en docs y defensa)

- **El lado del marketplace está simulado.** La integración real queda validada por contrato, no por uso en producción.
- **El catálogo de publicaciones es sintético.** Los SKU se muestrean del feed real, pero los atributos de publicación no son reales.
- **Sin gestión de ventas no se puede cerrar el lazo.** El sistema no sabe si hubo sobreventa: solo puede demostrar que propagó a tiempo. La métrica que importa en el negocio (cancelaciones) queda fuera de lo que este sistema mide.
- **La consistencia es eventual por diseño.** Hay una ventana entre la venta en la fuente y su reflejo en la tienda. El sistema la acota y la mide; no la elimina.
- **La escala real del dominio excede la del MVP.** Las fuentes llegan a millones de SKU; el MVP demuestra el mecanismo en el orden de 10⁵ vínculos e identifica los cuellos de botella.
- **Un solo formato de origen probado a fondo:** solo el `.csv` se ejercita contra una fuente real.
