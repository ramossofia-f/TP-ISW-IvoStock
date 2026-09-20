# PRD — Ivo Stock

**Sincronización de inventario entre N fuentes de stock y K tiendas de MercadoLibre**

| **Versión** | 00 — tentativo  |
|---|---|
| **Estado** | Borrador, sujeto a la aprobación del proyecto por la cátedra |
| **Documento anterior** | [validacion.md](validacion.md) |
---

## 0. Origen del proyecto

Ivo Stock nace de una necesidad comercial real: un seller multi-tienda de MercadoLibre que hoy sostiene la sincronización de stock de sus proveedores con un sistema a medida por cada par proveedor-tienda. El sistema que la empresa tiene en mente cubre **dos pilares: la sincronización de stock multi-bodega / multi-tienda y la gestión de la venta** hasta la entrega al transporte. **Este proyecto toma solo el primero.** El recorte es de alcance, no de interés: el trabajo tenía que entrar en los tiempos de la cursada, y el pilar de ventas (reservas, transferencias entre bodegas, consolidación internacional, couriers y etiquetas) depende de circuitos logísticos e integraciones con sistemas de bodega que no se pueden montar ni simular con honestidad en ese plazo.

De ese sistema se heredan tres reglas invariantes, que cualquier implementación de este proyecto debe poder verificar:

- **INV-1.** Una publicación tiene un único vínculo activo que le escribe stock en todo momento.
- **INV-2.** El stock de un SKU se ofrece completo en todas las tiendas vinculadas: no se reparte ni se topea. La sobreventa por ventas simultáneas es un **riesgo aceptado**, no un defecto a corregir.
- **INV-3.** Un proveedor que deja de cumplir el contrato se degrada a stock cero de forma paulatina, sin bloquear el pipeline del resto.


## 1. Problema y contexto desde la perspectiva de un multi-seller sin un integrador general

Un seller que vende en MercadoLibre en varios países se abastece de varios proveedores (bodegas propias, distribuidores, importadores) y cada uno le informa el stock a su manera: un `.csv` en un SFTP, un endpoint HTTP que devuelve texto plano, una tabla en una base de datos etcétera. Del otro lado, cada tienda de MercadoLibre es una cuenta distinta, con su propio catálogo y su propia autenticación.

Hoy cada conexión entre un proveedor y una tienda se resuelve con un script a medida. El costo no está en integrar un proveedor: está en que **integrarlo una vez no alcanza**. El mismo feed, parseado de la misma forma, se lee y se mantiene una vez por cada tienda. El trabajo crece con el producto de proveedores por tiendas, no con la suma. En el caso real que motiva el proyecto eso da **7 sistemas separados para sostener 2 fuentes de stock**.

Las consecuencias que el usuario sufre, en orden de dolor:

1. **Sobreventa.** La misma unidad queda ofrecida en varias tiendas a la vez; la primera venta deja sobrevendidas a las demás. Se paga en cancelaciones y en reputación de la cuenta.
2. **Oferta no publicada.** Sumar un proveedor o abrir una tienda nueva requiere desarrollo, así que no se hace, y el stock  no se ofrece.
3. **Ceguera operativa.** Cuando una publicación deja de actualizarse, nadie se entera hasta que se vende algo que no existe. No hay un lugar donde ver qué se escribió, cuándo y con qué resultado.


Publicar en una tienda el stock que está en otra fuente **sin sincronización confiable es peor que no publicarlo**: la misma unidad queda ofrecida en varias vitrinas y la primera venta deja sobrevendidas a las demás. El stock sigue aislado por que el limitante, ni comercial ni logístico, es la ausencia de un mecanismo de sincronización confiable.

El sistema que este PRD describe existe para que **agregar un proveedor o una tienda sea cargar configuración y no escribir código**, y para que el estado de esa sincronización sea observable.



## 2. Usuarios y casos de uso

### 2.1 Usuarios

| Usuario | Qué le importa | Qué hace en el sistema |
|---|---|---|
| **Responsable de catálogo** | Que todo el stock disponible esté ofrecido en todas las tiendas donde se pueda vender | Conecta y desconecta proveedores y tiendas, con sus credenciales; revisa los vínculos SKU ↔ publicación sugeridos, los aprueba o descarta, prende y apaga vínculos |
| **Responsable de publicaciones** | Que ninguna publicación quede desactualizada sin que nadie lo sepa | Monitorea el tablero de salud, investiga vínculos en falla y *dead letters*, decide qué hacer con las publicaciones muertas |



Los dos perfiles son **responsabilidades organizativas, no roles del sistema**: describen quién hace qué en el equipo del seller, y sirven para leer los casos de uso. El sistema no los implementa como roles con permisos diferenciados dado que todo usuario autenticado puede operar cualquier configuración.

### 2.2 Casos de uso

**CU-01 — Conectar un proveedor nuevo.** El responsable de catálogo elige el formato (`.csv` o tabla PostgreSQL), completa el origen y la identificación de los campos SKU y stock, ve un *preview* de las primeras filas ya parseadas, confirma que el sistema interpretó bien el formato, le asigna una prioridad y guarda. El sistema valida con un fetch de prueba y el proveedor queda *validado*.
*Éxito:* el proveedor quedó validado sin que nadie escriba una línea de código.
*Fracaso esperado:* el preview muestra basura o el fetch de prueba falla; el proveedor no se guarda como validado y el usuario corrige la configuración.

**CU-02 — Conectar una tienda de MercadoLibre.** El responsable de catálogo inicia el flujo OAuth 2.0, autoriza la aplicación en MercadoLibre y vuelve al sistema. En background arranca la lectura del catálogo, en dos etapas: primero se traen los **identificadores de publicación (MLX)** de la tienda y, cuando esa lista está completa, se **completan los datos de cada uno** —stock y demás atributos—. Recién con las dos etapas terminadas el catálogo está conformado.
*Éxito:* la tienda queda autenticada y su catálogo disponible para vincular, con el stock vigente de cada publicación.
*Fracaso esperado:* la lectura del catálogo falla o queda incompleta. No es catastrófico: se notifica, y el usuario puede vincular con lo que se leyó o cargar IDs a mano (CU-03).
*Nota de diseño:* esta lectura inicial dispone de toda la cuota de la tienda, porque en ese momento la tienda todavía no tiene vínculos y no hay actualizaciones que competir. La competencia por la cuota aparece después, con los webhooks, la validación de IDs cargados a mano y cualquier relectura manual sobre una tienda ya operativa: todas esas llamadas comparten los mismos 60 req/min con la escritura de stock (RF-48).

**CU-03 — Completar el catálogo a mano.** El responsable de catálogo pega una lista de IDs de publicación. El sistema los busca en la API, se queda con los que existen y no tenía, e informa los que descartó.

**CU-04 — Vincular un proveedor con una tienda.** Elegido el par proveedor validado + tienda autenticada, el sistema cruza los SKU de la fuente contra el catálogo de la tienda y sugiere las coincidencias. El usuario acepta todas, algunas o ninguna, y puede buscar y excluir casos puntuales. Al crearse cada vínculo, el sistema **compara el stock del proveedor contra el stock que MercadoLibre reporta** para esa publicación —dato que ya tiene del catálogo— y **encola como tareas de actualización solo las diferencias**.
*Éxito:* los vínculos aprobados quedan activos, y las publicaciones cuyo stock no coincidía con la fuente quedan encoladas para corregirse.
*Precondición:* el proveedor tiene al menos una corrida aceptada. Su lista de SKU sale de ahí, no del fetch de prueba del alta, que trae apenas un puñado.

**CU-05 — Cortar la alimentación de una publicación.** El usuario apaga un vínculo, da de baja un proveedor o desconecta una tienda. Los tres son el mismo hecho —una publicación deja de tener quién le escriba stock— y el sistema responde igual en los tres casos: **lleva a cero el stock de las publicaciones alcanzadas** y recién entonces desactiva el vínculo. Lo que apagó hoy puede volver a prender mañana, y al revés.
*Por qué siempre cero y nunca "dejarlo como está":* una publicación que se queda con el último stock conocido sigue vendiendo unidades que ya nadie respalda. Cortar la alimentación sin cortar la oferta es la forma más directa de producir sobreventa, y es justamente lo que el sistema existe para evitar.
*Fracaso esperado:* en una desconexión de tienda el token se revoca antes de que la cola se drene, y los ceros pendientes terminan en *dead letter* con su traza. El sistema no lo oculta: encola los ceros primero y revoca el token al final (RF-42).

**CU-06 — Diagnosticar una actualización que falló.** El responsable de publicaciones entra al tablero de salud, ve las *dead letters*: actualizaciones rechazadas con error no reintentable o que agotaron sus intentos. Para cada una tiene el delta, la respuesta de la API y el momento de la falla. Decide: reintentar, apagar el vínculo, o marcar la publicación como muerta.

**CU-07 — Operar con una fuente degradada.** El feed de un proveedor deja de responder, o una corrida llega corrupta. El sistema alerta, pone al proveedor en estado *degradado*, deja la corrida en cuarentena y **no propaga nada** de esa fuente. Las demás siguen funcionando. El usuario decide si espera o interviene.

Para decidir si una corrida está corrupta, el sistema calcula un **coeficiente de sospecha** `p ∈ [0,1]` y la pasa a cuarentena si `p > 0.5`. Se calcula contra el último snapshot válido del mismo proveedor, a partir de dos señales:

| Señal | Qué mide | Cómo se calcula |
|---|---|---|
| `D` | SKU que desaparecieron | SKU que estaban en el snapshot previo y no vienen en esta corrida, sobre el total del snapshot previo |
| `Z` | Ceros nuevos en masa | SKU que pasan de stock > 0 a stock 0, sobre los que tenían stock > 0 en el snapshot previo |

Cada señal se normaliza contra su tolerancia y se combinan con un *noisy-OR*:

```
d = min(1, D / 0.10)
z = min(1, Z / 0.25)

p = 1 - (1 - d)(1 - z)
```

Se eligió *noisy-OR* y no un promedio ponderado porque una sola señal en su tope tiene que alcanzar para frenar la corrida: con suma ponderada, un feed que llega **vacío** (`D = 1`) no supera 0.5 salvo que se le asigne a esa señal un peso mayor que el de todas las demás juntas.

**Ausencia y cero son lo mismo.** Cada corrida aceptada informa el stock completo del proveedor, no un incremento: un SKU que estaba en el snapshot previo y no viene en esta corrida **vale cero**, exactamente igual que si viniera con un cero explícito (RF-22). No se conserva su valor vigente. La razón es la misma que ordena todo el sistema: un SKU que el proveedor dejó de informar es un SKU que ya no puede respaldar, y sostener su último valor conocido es publicar oferta que no existe. Eso convierte a `D` en la señal crítica del coeficiente y no en una curiosidad estadística: **`D` es exactamente la proporción del catálogo previo del proveedor que la corrida está por poner en cero**, y los vínculos activos son un subconjunto de ese catálogo. La tolerancia de `0.10` deja entonces de medir "cuántos SKU faltan" y pasa a medir "cuánta oferta estoy dispuesto a apagar de golpe sin que lo revise una persona".

**Los errores de parseo se tratan aparte, como diagnóstico y no como guarda.** Una fila cuyo valor de stock es un texto o un número negativo es un **error de parseo** y se descarta. Un valor en blanco **no** es un error de parseo: se interpreta como **sin stock**, es decir `0`, y el SKU no conserva su valor vigente. Cuando los errores de parseo superan el **10 % de las filas** de una corrida, el sistema emite una **alerta** al responsable de publicaciones, sin detener la corrida.

Que la alerta no frene nada no deja un agujero, porque las dos formas en que un feed roto se manifiesta ya están cubiertas por el coeficiente: **una fila descartada es un SKU ausente**, que es lo que mide `D`, y **una columna de stock que llega vacía es un cero**, que es lo que mide `Z`. Un cambio de encoding que vuelva ilegible medio archivo dispara `D`; un archivo que llega con la columna de stock en blanco dispara `Z`. La tasa de parseo dice *qué* se rompió; `D` y `Z` deciden *si* se propaga. Por la misma razón, la basura crónica de un feed no inflama `D`: esos SKU tampoco estaban en el snapshot previo, así que no cuentan como desaparecidos.

**Primera corrida.** No hay snapshot previo, así que `D` y `Z` no existen y el coeficiente no se evalúa: la corrida se acepta y queda como línea de base. Tampoco puede propagar nada, y no por una excepción sino por construcción — vincular exige una corrida aceptada (RF-16), así que en la primera todavía no hay ningún vínculo. Eso acota su modo de falla: una primera corrida truncada produce **menos SKU**, y los SKU ausentes no generan vínculos. El resultado es menos oferta publicada, nunca stock en cero.

El coeficiente es un *score* con tolerancias fijas, no una probabilidad calibrada. Es además el punto de enganche del componente de ML de la Entrega 3 (sección 10): mismas señales, mismo umbral, pero los pesos aprendidos sobre corridas etiquetadas en lugar de tolerancias puestas a mano.

**CU-08 — Operar con una tienda degradada.** La API de MercadoLibre se cae, revoca un token o el worker acumula retraso por encima del umbral. El sistema marca la tienda como *degradada*, deja de consumir la cola para ella, conserva el trabajo pendiente y alerta al usuario para que continúe manualmente desde el frontend de MercadoLibre.

El umbral de retraso es **12 horas**: si existe una tarea de actualización encolada para esa tienda que lleva más de 12 horas sin aplicarse, la tienda pasa a *degradada*. Es un techo, no un objetivo — el objetivo es el p95 de 6 horas de RNF-01. La razón de que sean horas y no minutos es aritmética y está en el límite de la API: **60 req/min por tienda son 3.600 actualizaciones por hora**, así que una corrida grande de un proveedor con muchos vínculos ocupa la cola de una tienda durante horas sin que nada esté fallando. Un umbral de minutos declararía degradada a una tienda perfectamente sana cada vez que llega trabajo real, y una alerta que se dispara en operación normal es una alerta que el operador aprende a ignorar.

**CU-09 — Auditar qué se escribió.** Cualquiera de los dos usuarios consulta, para un SKU o una publicación, el historial de actualizaciones: qué valor tenía, qué valor se envió, cuándo y qué respondió la API.

## 3. Requisitos funcionales

Priorizados con **MoSCoW**. *Must* = sin esto el sistema no cumple su propósito y no se entrega. La columna *Entrega* indica el hito objetivo (POC = Entrega 2, MVP = Entrega 3).

Los IDs son estables: cuando un requisito se elimina, su número **no se reutiliza ni se renumera**, para que el SRD, los ADRs y el código puedan referenciarlo sin ambigüedad. Por eso **no existe RF-02** (control de acceso por rol, descartado: los perfiles son responsabilidades organizativas) ni **RNF-15** (rotación de credenciales de proveedor, sin justificación en este alcance). Los requisitos agregados después de la primera numeración van al final de la lista, no intercalados, así que el orden de los IDs no es el orden de lectura.

### Cuentas y acceso

| ID | Requisito | Prioridad | Entrega |
|---|---|---|---|
| RF-01 | Registro y login de usuarios; toda operación de configuración exige sesión autenticada | Must | POC |
| RF-03 | Credenciales de proveedores y tokens OAuth almacenados cifrados y nunca expuestos en la interfaz ni en logs | Must | POC |
| RF-41 | Toda acción disponible en la interfaz es ejecutable por una vía programática, con la misma autenticación y la misma traza | Should | MVP |
### Proveedores (fuentes de stock)

| ID | Requisito | Prioridad | Entrega |
|---|---|---|---|
| RF-04 | Alta de proveedor con formato `.csv` desde SFTP, endpoint HTTP o URL, configurando separador, presencia de encabezado y posición (o nombre) de los campos SKU y stock | Must | POC |
| RF-05 | Alta de proveedor con conexión a tabla de PostgreSQL, configurando tabla y nombre de columna de SKU y de stock | Must | MVP |
| RF-06 | Preview *best-effort* de las primeras filas parseadas antes de guardar el alta | Must | POC |
| RF-07 | Validación del alta con un fetch de prueba de algunos SKU con su stock; sin validación exitosa el proveedor no queda *validado* | Must | POC |
| RF-08 | Prioridad por proveedor (Baja / Media / Alta), modificable | Must | POC |
| RF-09 | Modificación y baja de proveedores | Should | MVP |
| RF-10 | Programación de la frecuencia de ingesta por proveedor | Should | MVP |

### Tiendas y catálogo

| ID | Requisito | Prioridad | Entrega |
|---|---|---|---|
| RF-11 | Alta de tienda por flujo OAuth 2.0 completo, con renovación automática de tokens | Must | POC |
| RF-12 | Lectura en background del catálogo de una tienda al darla de alta, en dos etapas: recuperación de los identificadores MLX y, al completarse, carga del stock y los atributos de cada publicación. Con notificación si alguna etapa falla o queda incompleta | Must | POC |
| RF-13 | Mantenimiento del catálogo por webhooks de publicación nueva | Must | MVP |
| RF-14 | Carga manual de IDs de publicación, validados contra la API; se incorporan los que existen y no estaban | Should | MVP |
| RF-15 | Vista de tiendas conectadas con su estado y sus vínculos | Must | MVP |
| RF-42 | Desconexión de una tienda: se encola **stock cero para todos sus vínculos** (RF-47), se revoca el token **una vez drenada esa cola**, los vínculos quedan desactivados y el catálogo deja de mantenerse. Si la revocación es externa y los ceros no se pueden escribir, quedan en *dead letter* con su traza. La historia de actualizaciones se conserva | Should | MVP |

### Vinculación

| ID | Requisito | Prioridad | Entrega |
|---|---|---|---|
| RF-16 | Sugerencia de vínculos SKU ↔ publicación por coincidencia de SKU, para un par proveedor validado + tienda autenticada, en cualquier momento. Requiere al menos una corrida aceptada del proveedor: su lista de SKU sale de ahí | Must | POC |
| RF-43 | Al crearse un vínculo, comparar el stock del proveedor contra el stock que MercadoLibre reporta para esa publicación y encolar como tarea de actualización solo las diferencias | Must | POC |
| RF-17 | Aprobación total, parcial o nula de las sugerencias, con búsqueda y exclusión de casos puntuales | Must | POC |
| RF-18 | Vínculo como interruptor ON/OFF; el OFF propaga stock cero a la publicación de ese vínculo, según la regla única de corte (RF-47) | Must | POC |
| RF-19 | Un SKU puede estar vinculado a publicaciones de varias tiendas; cada tienda ve el stock informado por la fuente, sin reparto ni topeo (**INV-2**) | Must | POC |
| RF-39 | Una publicación admite un único vínculo activo: el intento de vincular una publicación ya vinculada se rechaza con error (**INV-1**) | Must | POC |

### Sincronización

| ID | Requisito | Prioridad | Entrega |
|---|---|---|---|
| RF-20 | Ingesta re-ejecutable por proveedor, con snapshot crudo e inmutable de cada corrida | Must | POC |
| RF-21 | Normalización de la corrida con descarte trazado. Un stock de texto o negativo es **error de parseo** y la fila se descarta. Un stock en blanco **se interpreta como sin stock (0)**, no como dato ausente: el SKU no conserva su valor vigente. Un SKU repetido no es error de parseo: vale la última ocurrencia de la corrida y el descarte queda registrado. Descartar una fila no preserva el SKU: al no quedar en la corrida, el estado vigente lo lleva a cero (RF-22) | Must | POC |
| RF-44 | Alerta al superar el **10 % de filas con error de parseo** en una corrida, sin detener la corrida | Should | MVP |
| RF-22 | Cada corrida aceptada **reemplaza** el estado vigente del proveedor (SKU → stock): la corrida informa el inventario completo, no un incremento, y un SKU que no aparece **vale cero**, igual que si viniera con cero explícito. Ese estado es el único producto de la ingesta: no escribe en ninguna tienda | Must | POC |
| RF-45 | Cada actualización del estado vigente notifica a un worker que **compara el stock de los vínculos de ese proveedor contra el estado vigente** y encola una tarea de actualización **solo por cada diferencia** | Must | POC |
| RF-46 | Encolar es idempotente por vínculo: la cola admite **a lo sumo una tarea pendiente por vínculo** y una tarea nueva **reemplaza** a la pendiente en lugar de acumularse, conservando su posición de prioridad. Se escribe el último valor conocido, nunca una secuencia de valores viejos | Must | POC |
| RF-23 | Cola de trabajo con prioridad heredada del proveedor | Must | POC |
| RF-24 | Escritura de stock contra la API respetando el límite de consumo por tienda —**60 req/min**— con espera cuando se agota la cuota | Must | POC |
| RF-48 | El límite de consumo es **por tienda y compartido** entre la escritura de stock y la lectura de catálogo (webhooks, validación de IDs cargados a mano, relecturas manuales). Todas las llamadas a una tienda pasan por el mismo control de cuota; la lectura de catálogo disparada a mano cede ante las tareas de actualización pendientes | Must | MVP |
| RF-25 | Idempotencia: reprocesar una corrida no produce efectos duplicados | Must | POC |
| RF-26 | Reintentos con backoff ante errores transitorios | Must | POC |
| RF-27 | *Dead letter* persistida y revisable para errores no reintentables, con el delta, la respuesta de la API y el momento de la falla | Must | MVP |
| RF-28 | Validación de la corrida y cuarentena ante corrupción severa; una corrida en cuarentena no propaga ningún delta | Must | MVP |
| RF-29 | Estado *degradado* por proveedor y por tienda, con alerta al usuario y suspensión de la propagación afectada. Para una tienda el disparador por retraso es una tarea de actualización **encolada más de 12 horas** sin aplicarse | Must | MVP |
| RF-47 | **Regla única de corte:** apagar un vínculo, dar de baja un proveedor y desconectar una tienda disparan la misma acción — encolar stock cero para todas las publicaciones alcanzadas y desactivar el vínculo recién después. Ninguna publicación queda ofreciendo el último stock conocido de una fuente que dejó de alimentarla | Must | POC |
| RF-40 | Baja de un proveedor: aplica RF-47 sobre todos sus vínculos **de forma paulatina**, sin que esa baja masiva detenga el procesamiento del resto (**INV-3**) | Should | MVP |

### Observabilidad y operación

| ID | Requisito | Prioridad | Entrega |
|---|---|---|---|
| RF-30 | Auditoría de toda actualización intentada: SKU, publicación, valor anterior, valor enviado, respuesta de la API, timestamp | Must | POC |
| RF-31 | Tablero de salud: estado por feed y por tienda, vínculos en falla, dead letters, latencia de propagación | Must | MVP |
| RF-32 | Detección y marcado de publicaciones muertas: tras **5 fallos consecutivos** el vínculo deja de generar pedidos de actualización y la publicación queda expuesta en el tablero | Should | MVP |
| RF-33 | Health checks y métricas expuestas por cada componente | Must | MVP |
| RF-34 | Reprocesamiento manual de una corrida en cuarentena o de una dead letter desde la interfaz | Could | MVP |

### Entorno de desarrollo y demostración

| ID | Requisito | Prioridad | Entrega |
|---|---|---|---|
| RF-35 | Simulador de MercadoLibre que implementa el contrato real: OAuth 2.0, catálogo, actualización de stock, webhooks, el límite de 60 req/min por tienda y los errores reintentables y no reintentables | Must | POC |
| RF-36 | Generador de catálogo sintético configurable (tiendas, publicaciones por tienda, proporción de SKU coincidentes con el feed real, publicaciones muertas, latencia y tasa de error) | Must | POC |
| RF-37 | Generador de feeds sintéticos configurable (volumen, separador, encabezado, filas corruptas, deriva de stock) | Must | POC |
| RF-38 | Interfaz de marketplace única con dos implementaciones detrás —simulada y real— seleccionables por configuración | Must | POC |

### Fuera de este PRD (*Won't have this time*)

- Gestión de ventas, reservas, despacho y logística — con todo lo que el sistema original construye alrededor: Buyer, transferencias entre bodegas, lote internacional, contratación de couriers, etiquetas de Colecta o Flex, buffer de cancelados y estados de terceros.
- **Publicaciones compartidas**: un MLX alimentado por varios proveedores a la vez. Acá una publicación tiene un único vínculo activo (RF-39).
- Pricing: el sistema no lee ni escribe precios.
- Creación de publicaciones: el sistema asume que la publicación existe.
- Reparación de publicaciones muertas: el sistema alerta, la decisión es humana y se ejecuta fuera.
- Reparto o topeo de stock entre tiendas.
- Gestión de inventario a nivel bodega (ubicaciones, movimientos, conteos).
- Reportería de negocio.
- Ingesta por streaming: las fuentes son archivos y endpoints con frecuencia de minutos u horas.
- Compensar lo que la fuente no ofrece: si el feed no lo expone, el sistema no lo emula.

## 4. Requisitos no funcionales

| ID | Requisito | Objetivo verificable |
|---|---|---|
| RNF-01 | **Latencia de propagación** | **p95 en menos de 6 horas y p100 en menos de 12 horas**, medido **desde que el sistema conoce el cambio hasta que la tienda lo refleja**, sobre el 100 % de los vínculos activos. Superar las 12 horas no es un incumplimiento silencioso: declara la tienda *degradada* (RF-29). No cuentan los vínculos inactivos por publicación muerta o tienda degradada |
| RNF-01b | **Latencia de la fuente** | El sistema tolera fuentes con hasta **1 hora** de refresco. Esa latencia es anterior a la ventana de RNF-01 y no se le imputa |
| RNF-02 | **Throughput de ingesta** | Una corrida de 650.000 SKU procesada (descarga, parseo, normalización, cálculo de deltas) en menos de 10 minutos |
| RNF-03 | **No pérdida silenciosa** | Todo delta termina en uno de tres estados terminales: aplicado, en dead letter, o descartado por cuarentena con traza. Cero deltas sin estado |
| RNF-04 | **Idempotencia** | Reprocesar la misma corrida dos veces produce el mismo estado final y cero escrituras adicionales a la API. El encolado también es idempotente por vínculo (RF-46): N notificaciones sobre el mismo vínculo dejan una sola tarea pendiente, con el último valor |
| RNF-05 | **Degradación explícita** | Ante falla de una fuente o de una tienda, el sistema alerta y suspende solo la parte afectada; las demás siguen operando |
| RNF-06 | **Durabilidad de la cola** | Las tareas de actualización se persisten: una caída del worker o del broker con trabajo pendiente no pierde ninguna. Entrega al menos una vez, apoyada en la idempotencia de RNF-04. Como red de seguridad, una tarea perdida se vuelve a derivar comparando el estado vigente contra el último valor confirmado de cada publicación |
| RNF-06b | **Cota de la cola** | Por el reemplazo de RF-46, la cola pendiente de una tienda nunca supera su cantidad de vínculos activos, sin importar cuántas corridas se acumulen. Verificado inyectando corridas más rápido de lo que la cuota de 60 req/min permite drenar |
| RNF-07 | **Seguridad de credenciales** | Secretos solo por variables de entorno o almacén cifrado; cero credenciales en el repositorio, en la interfaz o en los logs. Verificado en CI |
| RNF-08 | **Control de acceso** | Ningún endpoint de configuración, consulta o auditoría responde sin sesión autenticada; verificado con tests. Sin distinción de permisos entre usuarios |
| RNF-09 | **Observabilidad** | Logging estructurado con identificador de corrida trazable de punta a punta, métricas por feed y por tienda, health check por componente |
| RNF-10 | **Levantamiento local** | `docker-compose up` (o un único target `make up`) levanta el sistema completo, incluido el simulador, sin credenciales externas. Procedimiento en el README |
| RNF-11 | **Readiness cloud** | Componentes sin estado local, configuración por entorno, imágenes construidas en CI |
| RNF-12 | **CI y testing** | Build y tests corriendo en CI desde la Entrega 2; los caminos de falla (cuarentena, dead letter, rate limit, token revocado) tienen test propio |
| RNF-13 | **Escalabilidad conocida** | El diseño soporta el orden de 10⁵ vínculos activos; los cuellos de botella hacia los **10⁸ que exige el sistema original** están identificados y explicados, sin implementar esa escala |
| RNF-14 | **Procesar cambios, no inventarios** | El trabajo contra el recurso escaso —la API— es proporcional a los deltas y no al catálogo: una corrida sin cambios produce **cero escrituras**. La comparación interna sí recorre los vínculos del proveedor, pero ocurre contra la base propia y no consume cuota. Verificado midiendo llamadas a la API por corrida contra cantidad de deltas |
| RNF-16 | **Contrato de la interfaz programática** | La vía programática de RF-41 está descrita en un formato legible por máquina (OpenAPI), versionado junto al sistema |

**De dónde salen las 6 y las 12 horas.** No son un número de confort: se derivan del único recurso que el sistema no controla. La API permite **60 req/min por tienda**, o sea **3.600 actualizaciones por hora**, **21.600 en 6 horas** y **43.200 en 12**. Ese es el techo de trabajo que una tienda puede absorber, y ninguna decisión de arquitectura propia lo mueve —ni más workers, ni más máquinas, ni una cola más rápida—. Un objetivo de minutos sería un objetivo que el sistema no puede cumplir ni fallar por mérito propio: lo cumpliría cuando el volumen de deltas fuera chico y lo incumpliría cuando fuera grande, midiendo el tamaño de la corrida y no la calidad de la implementación. Con el techo a 12 horas, en cambio, incumplir significa algo verificable —la cola no drena al ritmo que la cuota permite— y por eso la violación dispara el estado *degradado* en lugar de quedar en un reporte.

El mismo razonamiento explica por qué el **reemplazo por vínculo de RF-46** es un requisito y no una optimización: con 3.600 escrituras por hora como techo, una cola que acumula una tarea por cada corrida gasta la cuota escribiendo valores que ya están vencidos. El reemplazo hace que el trabajo pendiente sea proporcional a la **cantidad de vínculos desactualizados** y no a la cantidad de corridas atrasadas, que es la misma idea de RNF-14 aplicada a la cola.


## 5. Criterios de éxito

Medibles, y verificables desde el propio sistema:

1. **Integrar sin programar.** Dar de alta un proveedor nuevo con un formato ya soportado toma menos de 10 minutos y **cero líneas de código**. Se demuestra en vivo dando de alta una fuente que el equipo no usó durante el desarrollo.
2. **Escalar por configuración.** Conectar una tienda adicional al mismo proveedor no agrega componentes ni código: el catálogo se lee, los vínculos se sugieren y la sincronización arranca. Se demuestra pasando de 1 a K tiendas sobre el mismo feed.
3. **Propagación oportuna.** RNF-01 cumplido —p95 bajo 6 horas, ninguna tarea por encima de 12— medido sobre la métrica de latencia que el propio sistema expone, durante una corrida completa del feed real.
4. **Nada se pierde en silencio.** RNF-03 cumplido: la suma de deltas aplicados, en dead letter y descartados por cuarentena es igual al total de deltas calculados, en toda corrida.
5. **Cero propagación de basura.** Ninguna corrida marcada como corrupta produce escrituras a la API. Se demuestra inyectando un feed truncado con el generador sintético.
6. **El operador se entera.** Ante una tienda caída, un token revocado y un feed corrupto, el sistema produce la alerta correspondiente y el estado degradado queda visible en el tablero. Se demuestra provocando los tres casos.
7. **Trazabilidad completa.** Para cualquier publicación se puede reconstruir qué stock se le escribió, cuándo, desde qué corrida y de qué fuente.

## 6. Supuestos

| ID | Supuesto | Si es falso |
|---|---|---|
| S-01 | Las publicaciones ya existen en MercadoLibre; el sistema solo les escribe stock | Habría que crear publicaciones, que está explícitamente fuera de alcance |
| S-02 | El SKU es clave de cruce confiable entre el catálogo del proveedor y el de la tienda | El matching por SKU pierde sentido y haría falta un mecanismo de resolución de identidad, que no está en este alcance |
| S-03 | El stock que informa el proveedor es la verdad disponible; el sistema no lo audita contra la realidad física | El sistema propaga números equivocados sin poder detectarlo; se mitiga parcialmente con la validación de corrida |
| S-04 | El contrato de la API de MercadoLibre (OAuth 2.0, endpoints de catálogo y stock, webhooks, límites) se mantiene estable durante la cursada | La implementación real se rompe; el simulador mantiene el sistema demostrable mientras se adapta |
| S-05 | El acceso al feed real de Celesa (~650.000 SKU, actualización cada 30 minutos) sigue disponible para el equipo | Se trabaja con el generador de feeds sintéticos, que ya es parte del sistema |
| S-06 | Simular el marketplace es representativo del comportamiento real en lo que importa: autenticación, límites de consumo y taxonomía de errores | El sistema funcionaría contra el simulador y no contra la API real; se mitiga manteniendo una única interfaz de marketplace con implementación real intercambiable |
| S-07 | El volumen de deltas por corrida es una fracción chica del total de vínculos | El dimensionamiento cambia de orden: el sistema pasa de propagar cambios a reescribir catálogos, y RNF-01 deja de ser alcanzable con los límites de consumo de la API |
| S-08 | El límite de consumo de la API es de **60 requests por minuto por tienda**, extraído de la documentación oficial de MercadoLibre, y se mantiene durante el proyecto | El caudal máximo por tienda cambia y con él el dimensionamiento. Si baja, los objetivos de RNF-01 (p95 en 6 horas, p100 en 12) se cumplen para la parte prioritaria de la cola y no para toda: la prioridad por proveedor pasa de ser una comodidad a ser el mecanismo que decide qué se actualiza |

## 7. Limitaciones conocidas

Para ser honestos en la documentación y en la defensa:

- **El lado del marketplace está simulado.** Es una decisión deliberada dado que escribir stock sobre publicaciones productivas tiene consecuencias comerciales, y depender de credenciales privadas haría el sistema no corregible localmente.
- **El catálogo de publicaciones es sintético.** Los SKU se muestrean del feed real para que el matching se ejercite contra datos verdaderos de un lado, pero los atributos de publicación no son reales.
- **La API de MercadoLibre va a cambiar.** Es su plataforma y la versiona cuando quiere. El sistema no se blinda contra eso: lo absorbe. Todo el conocimiento del contrato vive detrás de la interfaz de marketplace (RF-38), así que un cambio se paga en un solo componente y no en el motor de sincronización.
- **La consistencia es eventual por diseño.** Entre que el proveedor vende una unidad y que la tienda lo refleja hay una ventana. El sistema la acota y la mide; no la elimina.
- **La escala real del dominio excede la del MVP.** Las fuentes relevadas llegan a millones de SKU; el MVP demuestra el mecanismo en el orden de 10⁵ vínculos e identifica los cuellos de botella para el resto.
- **Un solo formato de origen probado a fondo.** El contrato acepta `.csv` y PostgreSQL, pero solo el `.csv` se ejercita contra una fuente real.
- **La sobreventa no se elimina, se acota.** Ofrecer el stock completo en las K tiendas (**INV-2**) garantiza que dos ventas simultáneas sobre la última unidad colisionen. El sistema reduce la ventana, no la cierra.
    
## 8. Riesgos

Clasificados con **ROAM**: *Owned* (vigilado, sin plan todavía), *Mitigated* (hay plan activo), *Accepted* (se corre a sabiendas).

| ID | Riesgo | Prob. | Impacto | ROAM | Plan |
|---|---|---|---|---|---|
| **R-01** | El caudal de sincronización supera el límite de consumo de la API de MercadoLibre | Alta | Crítico | Owned | El límite es de **60 req/min por tienda** (documentación oficial de la API), o sea **3.600 actualizaciones por hora y por tienda**: es una cota dura que ninguna decisión de infraestructura propia mueve, y además es **compartida con la lectura de catálogo** (RF-48). Tres mecanismos la absorben: los objetivos de latencia se fijan en el orden de horas y se derivan de esa cota (RNF-01), el reemplazo por vínculo evita gastar cuota escribiendo valores ya vencidos (RF-46) y la prioridad por proveedor decide qué se actualiza primero cuando la cola no drena (RF-23). El simulador implementa el mismo límite (RF-35) para que el POC lo ejercite en serio. Es el riesgo técnico dominante y el que el POC tiene que dejar resuelto |
| **R-02** | Un feed corrupto propagado sin validar pone en cero el stock de miles de publicaciones | Media | Crítico | Mitigated | Coeficiente de sospecha y cuarentena por corrida (CU-07, RF-28). Se demuestra inyectando un feed truncado con el generador sintético |
| **R-03** | El cruce por SKU propone menos vínculos de los reales | Media | Medio | Mitigated | El matching es una **sugerencia**, no un automatismo: RF-17 permite buscar y vincular a mano, así que un error de cruce degrada el resultado sin bloquearlo |
| **R-04** | El sistema funciona contra el simulador y falla contra la API real | Media | Alto | Mitigated | Una única interfaz de marketplace con dos implementaciones (RF-38); el simulador implementa el contrato real, no uno conveniente. Queda como limitación declarada: la integración real está validada por contrato, no por producción |
| **R-05** | Las publicaciones muertas se acumulan sin que nadie las atienda | Media | Bajo | Mitigated | RF-32 las marca, corta sus llamadas y las expone en el tablero. El costo de no atenderlas es oferta perdida, no falla del sistema  |

## 9. Roadmap a POC y MVP

**POC (Entrega 2) — resolver el riesgo técnico.** El riesgo más grande es el motor de sincronización contra la API: límites de consumo, idempotencia y ciclo de vida de los tokens. El POC lo resuelve sobre una ruta completa y angosta: **un proveedor real (Celesa) + una tienda contra el contrato real de MercadoLibre**, con stock propagándose de punta a punta y auditado. Incluye el simulador y los generadores, porque sin ellos no hay forma de ejercitar los caminos de falla. Interfaz mínima. CI y tests operativos.

**MVP (Entrega 3) — generalizar y operar.** N proveedores por K tiendas, el segundo formato de origen (PostgreSQL), webhooks de catálogo, cuarentena, dead letters, estados degradados, tablero de salud completo y observabilidad verificable. Más el componente de ML, una vez definido.

## 10. Pendiente de definir

- **El componente de Machine Learning** que exige la Entrega 3: **detección de anomalías en corridas de feed**, alimentada por datos que el sistema ya genera (histórico de snapshots y auditoría de actualizaciones). Reemplaza las tolerancias fijas del coeficiente de CU-07 por pesos aprendidos sobre corridas etiquetadas, sobre las mismas señales. Se decide antes de cerrar la Entrega 1 y se registra con un ADR.


## 11. Glosario

Los términos se usan como los define el sistema original, recortados a lo que existe en este alcance.

| Término | Definición |
|---|---|
| **Proveedor** | Una fuente de stock: propia o de un tercero, indistinto. Lo que varía es el origen (`.csv` sobre SFTP / endpoint / URL, o tabla PostgreSQL) y las credenciales. Es la **bodega** del sistema original |
| **Tienda** | Una cuenta de MercadoLibre de la empresa, con su catálogo y su autenticación propia. Es la **vitrina** del sistema original; "sitio" es el término de MercadoLibre para lo mismo |
| **SKU** | El identificador de un producto en el catálogo de un proveedor. En este dominio es el **ISBN**, que es lo que hace posible cruzar catálogos entre fuentes y contra MercadoLibre |
| **MLX** | El identificador de una publicación de MercadoLibre. La X es el país: `MLA1234`, `MLC1234` |
| **Vínculo** | La unidad de trabajo del sistema: la relación entre un SKU de un proveedor y un MLX de una tienda. Es un **interruptor** ON/OFF, no un alta y una baja: apagarlo conserva su historia |
| **Corrida** | Una ejecución de ingesta sobre un proveedor: descarga, snapshot, normalización, validación y cálculo de deltas |
| **Snapshot** | La copia cruda e inmutable de lo que la fuente devolvió en una corrida, guardada tal cual llegó. Es lo que permite reprocesar y auditar |
| **Estado vigente** | El stock que el sistema da por bueno para cada SKU de un proveedor. Cada corrida aceptada lo **reemplaza** completo: un SKU que no viene en la corrida queda en cero. Es el único producto de la ingesta y la entrada del worker comparador |
| **Delta** | Un cambio de stock de un SKU respecto del último estado conocido. Es lo único que se propaga: el sistema procesa cambios, no inventarios completos |
| **Publicación muerta** | Un MLX que rechaza actualizaciones de forma persistente (5 fallos consecutivos). El sistema la marca, deja de emitirle pedidos y la expone. **No la repara** |
| **Dead letter** | Una actualización que falló con error no reintentable o que agotó sus intentos, persistida con su delta, la respuesta de la API y el momento de la falla, para revisión humana |
| **Cuarentena** | El estado de una corrida cuyo coeficiente de sospecha superó el umbral. Una corrida en cuarentena **no propaga ningún delta** |
| **Degradado** | El estado de un proveedor cuya fuente no responde o entrega corridas corruptas, o de una tienda cuya API falla o tiene una tarea encolada hace más de **12 horas**. La propagación afectada se suspende; el resto sigue operando |
| **Sobreventa** | Vender en dos tiendas la misma unidad física. Consecuencia aceptada de ofrecer el stock completo en todas las tiendas vinculadas |
| **Simulador de marketplace** | La implementación local del contrato de MercadoLibre (OAuth 2.0, catálogo, stock, webhooks, límites y errores) contra la que se desarrolla y se demuestra el sistema. Está detrás de la misma interfaz que la implementación real |
