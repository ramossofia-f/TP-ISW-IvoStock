# Ivo Stock

Sincronización de inventario entre proveedores HTTP y tiendas de un marketplace simulado.

Equipo: María Saráchaga, Francisco Ortega y Sofía Ramos. Entrega 2: 27/10/2026. Entrega 3: 24/11/2026.

## Problema y propuesta

Un vendedor con varios proveedores y tiendas mantiene conexiones independientes para cada par. Incorporar una tienda obliga a repetir lecturas y lógica de integración, y resulta difícil saber qué publicaciones están actualizadas. En el caso que motiva el proyecto, siete sistemas separados sostienen dos fuentes de stock: el trabajo crece con el producto de proveedores por tiendas y no con su suma. Una sincronización atrasada o incorrecta produce sobreventa, cancelaciones y pérdida de reputación.

Ivo Stock ingiere cada proveedor una vez y reutiliza su inventario para todas las tiendas vinculadas. El operador configura fuentes, incorpora tiendas, aprueba coincidencias por SKU y consulta pendientes y fallas. El motor continúa procesando con la interfaz detenida, siempre que los almacenes estén disponibles.

El POC se opera por CLI y demuestra una fuente real archivada hasta una tienda simulada. El MVP incorpora una interfaz con cuentas precreadas, login, configuración y tablero; permite incorporar una segunda tienda desde la app. Los perfiles de catálogo y publicaciones son responsabilidades de uso, con los mismos permisos.

## Reglas del dominio

- INV-1: una publicación tiene como máximo un vínculo activo que escribe su stock. Un vínculo en falla conserva esa asignación.
- INV-2: cada tienda recibe todo el stock del proveedor. Las ventas simultáneas pueden producir sobreventa; es un riesgo aceptado.
- INV-3: dar de baja un proveedor lleva sus publicaciones a cero mediante trabajo durable, sin detener otras integraciones. Una caída transitoria congela su propagación y no produce ceros.

El catálogo se prepara antes de incorporar la tienda y sus publicaciones permanecen estáticas; las cantidades sí cambian. El sistema sincroniza inventario. Las ventas, la logística y las decisiones comerciales se resuelven fuera de la aplicación.

## Casos de uso

| ID | Recorrido y resultado |
|---|---|
| CU-01 | Incorporar un proveedor: indicar nombre y URL, comprobar el contrato, revisar una muestra y las coincidencias; guardar una configuración validada con su primera ingesta programada |
| CU-02 | Incorporar una tienda preparada: importar su catálogo por HTTP en segundo plano, consultar su progreso y dejarlo disponible para vincular |
| CU-03 | Sugerir coincidencias exactas de SKU y aprobar todas, una selección o una cantidad; rechazar publicaciones ya asignadas |
| CU-04 | Ingerir el inventario, validar la corrida y propagar únicamente las diferencias necesarias |
| CU-05 | Apagar un vínculo o dar de baja un proveedor; conservar la intención hasta confirmar el cero |
| CU-06 | Consultar corridas, stock deseado y confirmado, pendientes, cuarentenas y fallas |
| CU-07 | Revisar una falla y reanudar por CLI con el stock deseado vigente; reproducir una corrida por el circuito normal |

## Requisitos funcionales

Must significa necesario para el hito indicado. POC corresponde a E2 y MVP a E3. La interfaz gráfica de las operaciones del POC se implementa en el MVP.

| ID | Requisito | Prioridad | Hito |
|---|---|---|---|
| RF-01 | Operadores individuales precreados, login y operaciones autenticadas en la aplicación | Must | MVP |
| RF-02 | Alta de proveedor por URL HTTP, validación y preview antes de considerarlo válido | Must | POC |
| RF-03 | Ingesta automática con intervalo global de 300 minutos, sin corridas simultáneas del mismo proveedor; la primera vence 300 minutos después del alta. Disparo manual independiente y adelanto del vencimiento por CLI | Must | POC |
| RF-04 | Modificación de nombre y URL del proveedor con nueva validación | Should | MVP |
| RF-05 | Incorporación de tiendas simuladas con credenciales preconfiguradas e importación inicial de catálogo paginado en segundo plano, con progreso consultable y reanudación desde la última página confirmada | Must | POC |
| RF-06 | Coincidencia exacta por SKU contra la validación del alta o la última corrida aceptada; búsqueda y aprobación total, selectiva o por cantidad. Los vínculos aprobados antes de la primera corrida aceptada esperan sin generar escrituras | Must | POC |
| RF-07 | Rechazo de una segunda asignación activa a la misma publicación | Must | POC |
| RF-08 | Un SKU puede abastecer publicaciones de varias tiendas con su cantidad completa | Must | POC |
| RF-09 | Apagado de vínculo con intención de cero persistida y desactivación únicamente tras confirmarlo | Must | POC |
| RF-10 | Snapshot crudo e inmutable de cada descarga, conservado antes de aceptar la corrida | Must | POC |
| RF-11 | Contrato UTF-8 con primera fila exacta `SKU;stock`, separador `;` y dos columnas. SKU como cadena; blanco es cero; stock negativo, no entero o fuera de rango y filas mal formadas se descartan con línea y motivo. Entre duplicados vale la última ocurrencia válida | Must | POC |
| RF-12 | Cada corrida aceptada representa el inventario completo; los SKU ausentes pasan a cero. Aceptar actualiza atómicamente el estado y su evento de comparación | Must | POC |
| RF-13 | Validar contra el último inventario aceptado y poner en cuarentena corridas sospechosas sin modificarlo ni generar nuevas tareas | Must | POC |
| RF-14 | Informar tasa de errores de parseo y alerta al superar 10 %, sin detener por esa tasa sola | Must | POC |
| RF-15 | Comparar por vínculo contra su último stock confirmado; al vincular, usar la cantidad importada del catálogo | Must | POC |
| RF-16 | Cola durable FIFO entre tareas disponibles, con una pendiente por vínculo; el último valor reemplaza al anterior conservando antigüedad. Los reintentos en espera no bloquean otras tareas | Must | POC |
| RF-17 | Compartir 60 llamadas/minuto por tienda entre lecturas y escrituras, contando intentos fallidos y conservando la cuota al reiniciar | Must | POC |
| RF-18 | Reintentar errores transitorios con backoff. Gestionar 429 mediante espera, sin dead letter ni consumo del presupuesto de fallos del vínculo | Must | POC |
| RF-19 | Persistir errores definitivos y reintentos agotados en dead letter; suspender el vínculo hasta revisión manual sin borrar evidencia | Must | POC |
| RF-20 | Baja de proveedor con propagación gradual de cero sobre sus vínculos | Must | POC |
| RF-21 | Consultar por vínculo deseado, confirmado, última confirmación, pendiente y falla; un intento fallido no modifica el confirmado | Must | POC |
| RF-22 | CLI para configurar, ingerir, vincular, consultar, monitorear cuota y progreso, cortar, reproducir corridas y reanudar fallas; reanudar usa el valor vigente y respeta cortes pendientes | Must | POC |
| RF-23 | Fuente inaccesible o corrida inválida: estado degradado y congelamiento de esa fuente; las restantes continúan | Must | POC |
| RF-24 | Fallas globales de acceso a una tienda: degradación y conservación de pendientes hasta recuperar acceso | Must | POC |
| RF-25 | Interfaz autenticada de configuración, búsqueda y tablero de corridas, tiendas, pendientes, confirmaciones y fallas | Must | MVP |
| RF-26 | Simulador HTTP con catálogo estático generado, cantidades absolutas, semántica de cero, límite de llamadas y errores provocables | Must | POC |
| RF-27 | Componente de ML con entrenamiento reproducible, inferencia y monitoreo; el problema y el modelo se definirán para E3 | Must | MVP |

## Validación de corridas

Sea `D` la proporción de SKU del último inventario aceptado que desaparecen y `Z` la proporción de sus SKU positivos que están presentes en la corrida con cero. Los ausentes sólo cuentan en `D`.

```text
d = min(1, D / 0.10)
z = min(1, Z / 0.25)
p = 1 - (1 - d) * (1 - z)
cuarentena si p > 0.5
```

Las tolerancias son fijas; el puntaje es determinista. La primera corrida establece la base sin evaluar D/Z; los vínculos aprobados antes de ella esperan sin escrituras y se comparan al aceptarla. Una fila descartada deja ausente su SKU salvo que exista otra ocurrencia válida. Una cuarentena puede reproducirse por CLI, con la misma validación; no existe aprobación que omita la guarda.

## Requisitos no funcionales

| ID | Objetivo verificable | Hito |
|---|---|---|
| RNF-01 | Feed real completo, aproximadamente 255.000 SKU: descarga, parseo, validación, persistencia y cálculo de diferencias en menos de 10 minutos | POC |
| RNF-02 | Dos tiendas con 1.000 vínculos cada una, sanas y sin cola previa: p95 de publicación <30 minutos y p99 <60 minutos desde aceptar la corrida o persistir el corte hasta su efecto externo | MVP |
| RNF-03 | Cero trabajo vigente perdido: todo cambio aceptado permanece reconstruible, pendiente, aplicado o en dead letter. Los reemplazos quedan identificados; una cuarentena no genera trabajo publicable | POC |
| RNF-04 | Con el mismo estado de entrada, repetir una corrida o notificarla varias veces no duplica pendientes ni produce escrituras adicionales. Repetir una petición tras perder su confirmación conserva el efecto absoluto | POC |
| RNF-05 | La cola pendiente por tienda está acotada por sus vínculos no desactivados, incluyendo cortes por confirmar | POC |
| RNF-06 | Diez cierres abruptos reproducibles, cero trabajo vigente perdido y reanudación en hasta 10 minutos con almacenes disponibles; comprobar también reinicio abrupto de PostgreSQL conservando volúmenes | POC |
| RNF-07 | Al menos 99 % de comprobaciones funcionales exitosas por separado para interfaz/API y motor durante 24 horas, con observador externo cada minuto | MVP |
| RNF-08 | Con PostgreSQL disponible, detener API no detiene el motor; detener workers permite consultar estado persistido. PostgreSQL es un punto común de falla | POC/MVP |
| RNF-09 | Cinco operadores autenticados a una consulta/s cada uno durante 30 minutos, sobre 2.000 vínculos y con motor activo: p95 <2 segundos | MVP |
| RNF-10 | Secretos por entorno, nunca en Git, respuestas de configuración o logs; snapshots reales y sus derivados fuera del repositorio | POC |
| RNF-11 | Configuración, estado y fallas sólo accesibles por operadores autenticados en la aplicación; health checks no contienen datos operativos | MVP |
| RNF-12 | CI con análisis estático, pruebas de fallas, integración, construcción de imágenes y verificaciones de documentación y secretos | POC |
| RNF-13 | Arranque local documentado con un comando después de instalar Docker y preparar configuración; sin credenciales externas | POC |
| RNF-14 | Procesos configurables por entorno e imágenes construibles en CI; los datos durables residen en PostgreSQL y S3 | POC |
| RNF-15 | Demostrar 2.000 vínculos totales, 1.000 por tienda; registrar recursos, cantidad y frecuencia de cambios sin imponer un máximo de deltas por tienda | MVP |
| RNF-16 | OpenAPI generado para los endpoints realmente implementados de API y simulador | POC/MVP |
| RNF-17 | Estado y registros estructurados correlacionables por corrida, vínculo, revisión e intento; health check por proceso y métricas operativas consultables | POC |

La espera hasta la siguiente ingesta puede ser de cinco horas y se informa separada de RNF-02. Las mediciones registran errores, rechazos, timeouts y solicitudes sin resultado; no se usan para mejorar percentiles. El protocolo detallado está en el [SRD](../srd/SRD.md).

## Datos, demostración y límites

La fuente real disponible es un snapshot archivado de Celesa, de aproximadamente 4 MB y 255.000 SKU. El original no tiene encabezado. La preparación conserva sus bytes y produce una copia con la cabecera requerida, accesible por HTTP; el manifiesto registra procedencia, fecha y hashes. La caracterización del feed (bytes, hash, filas, SKU, duplicados, ceros, tasa de errores de parseo y descartes con línea y motivo) se reproduce con [scripts/analizar_feed.py](../../scripts/analizar_feed.py), que aplica el mismo parser del motor: `uv run python scripts/analizar_feed.py data/feeds/ARCHIVO.csv`. Con dos snapshots calcula también `D`, `Z`, `p` y la cantidad de diferencias. Los resultados están en el [registro E2](../entregas/ENTREGA-2.md). Un proveedor de ensayo sirve el snapshot por HTTP y, en cada consulta, permuta las cantidades positivas del 40 % de los SKU, sin modificar el archivo base; `?no-changes=true` devuelve la versión archivada. La demostración identifica la reproducción de datos archivados y las variantes sintéticas utilizadas para cambios y fallas. No se inventa un histórico de corridas.

Los SKU del catálogo simulado se seleccionan del inventario preparado. El stock físico no puede verificarse y se acepta como información de la fuente. Una fuente congelada conserva el último stock publicado hasta recuperación o baja explícita. El marketplace es un servicio simulado del proyecto; su funcionamiento no acredita una integración productiva.

La disponibilidad se acredita sólo para la ventana medida. La escala de demostración no acredita capacidad ilimitada. El estado de implementación y las evidencias se mantienen en el [roadmap](../roadmap/ROADMAP.md).

## Supuestos y plan B

Cada supuesto separa la consecuencia de que sea falso del plan B: lo que el equipo hace en ese caso. Cuando no existe una alternativa se declara como riesgo aceptado.

| ID | Supuesto | Consecuencia si es falso | Plan B |
|---|---|---|---|
| S-01 | Las publicaciones ya existen en la tienda; el sistema sólo escribe su stock | Los SKU sin publicación quedan fuera de la sincronización | Las publicaciones faltantes se crean con la herramienta externa que el equipo ya opera. Después se reimporta el catálogo (RF-05) y se vinculan con el flujo habitual (RF-06), sin cambiar el alcance |
| S-02 | El SKU es una clave de cruce confiable entre proveedor y tienda | Las sugerencias automáticas pierden precisión | El SKU se trata como cadena exacta. Los casos dudosos se resuelven con búsqueda y aprobación selectiva (RF-06); los que no cruzan quedan sin vincular sin bloquear al resto |
| S-03 | El stock que informa el proveedor es la verdad disponible | Se propagan cantidades equivocadas sin poder detectarlo | Sin plan B dentro del sistema: riesgo aceptado. Auditar stock físico exige acceso a depósitos y reservar un margen contradice INV-2. Mitigación: la guarda de corridas (RF-13) frena errores masivos; ante un error puntual se apaga el vínculo (RF-09) o se da de baja el proveedor (RF-20) |
| S-04 | La tienda admite 60 llamadas/minuto compartidas entre lecturas y escrituras, con la taxonomía de errores simulada | Cambia el caudal por tienda y con él RNF-02 | El límite vive en un único módulo de cuota y en el simulador. Se ajusta ese valor, se recalcula RNF-02 con la misma aritmética y, si baja, se declaran los nuevos objetivos antes de medir |
| S-05 | El snapshot archivado de Celesa es representativo del feed real | Las mediciones de volumen y calidad no se trasladan a la fuente viva | Se repite la caracterización con [scripts/analizar_feed.py](../../scripts/analizar_feed.py) sobre cualquier snapshot nuevo. Si no hay acceso a la fuente, el generador sintético con semilla reproduce volumen, ceros, filas corruptas y deriva |
| S-06 | Entre corridas cambia una fracción chica del inventario | Las diferencias superan la cuota y la tienda se atrasa | La cola mantiene una tarea pendiente por vínculo (RF-16), así que el atraso queda acotado y visible (RNF-05). Se mide la fracción real con `D`, `Z` y el conteo de diferencias antes de comprometer RNF-02 |
| S-07 | El simulador representa al marketplace en autenticación, cuota y errores | El motor funciona contra el simulador y no contra la API real | El motor usa el marketplace sólo por HTTP (ADR-0006), así que una implementación real reemplaza al cliente sin tocar ingesta ni comparación. Mientras tanto, la integración real se declara validada por contrato y no en producción |
| S-08 | Tres integrantes sostienen el calendario del [roadmap](../roadmap/ROADMAP.md) hasta el 24/11/2026 | Los tramos del MVP no se completan en fecha | Si un tramo se atrasa más de dos días se recorta antes de empezar el siguiente: primero los *Should* (RF-04), después se reduce la escala medida (RNF-09, RNF-15). Recortar un *Must* exige revalidar con la cátedra |

## Criterios de aceptación

K = 2: el POC demuestra una tienda y el MVP, dos tiendas simuladas sobre el mismo proveedor.

| # | Criterio | Cómo se verifica | Hito |
|---|---|---|---|
| 1 | Configurar un proveedor válido e incorporar una tienda sin modificar código | Recorrido del README por CLI sobre el commit entregado, sin cambios en `src/` | POC |
| 2 | Recorrer el feed real completo hasta publicaciones simuladas y observar las confirmaciones | RNF-01 medido en el registro E2; `status links` muestra confirmado igual a deseado | POC |
| 3 | Repetir una corrida estable sin nuevas escrituras | RNF-04: prueba de integración en CI y cero intentos nuevos en el ensayo real | POC |
| 4 | Demostrar cuarentena, 429, dead letter, reanudación y corte confirmado a cero | RF-13, RF-18, RF-19, RF-22 y RF-09: pruebas automatizadas propias en CI y fallas provocadas en el simulador | POC |
| 5 | Recuperar trabajo vigente después de cierres abruptos | RNF-06: diez cierres reproducibles, cero trabajo vigente perdido y reanudación en hasta 10 minutos | POC |
| 6 | Incorporar desde la app la segunda tienda reutilizando la ingesta y medir los objetivos del MVP | Una sola corrida por proveedor alimenta ambas tiendas; RNF-02, RNF-07, RNF-09 y RNF-15 medidos con su protocolo del SRD | MVP |
