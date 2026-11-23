# Verificación de métricas y observador

Fecha: 17/11/2026. Desarrollo aislado en la rama `feat/metricas-disponibilidad`, inicialmente
basada en `1260c81`. La integración del monitoreo de ML incorpora localmente `5911066` del PR #18;
no modifica su worktree ni fusiona ese PR en GitHub.

## Alcance

Servicio interno con muestreo por minuto y retención de siete días, consultas autenticadas
compartidas con el tablero y observador HTTP sin persistencia ni alertas. Se reutilizan las
consultas operativas, sesiones y heartbeats; se agrega la información temporal que no existía
para medir publicación completa por revisión y tienda. Ver [ADR-0017](../adr/0017-metricas-y-observador.md).

## Comprobación

Entorno: Windows con Docker Desktop, contenedores Linux, PostgreSQL 15 y MinIO. Dependencias de
`uv.lock`; la suite completa instaló también el grupo `ml` en un entorno efímero del contenedor.
Proyecto de Compose `ivostock-metrics-check`, con volúmenes propios y puertos 18000–18003/18081;
el entorno de operación preexistente no se detuvo ni se migró. Los datos del recorrido son
sintéticos: diez SKU y cinco vínculos en cada tienda.

| Comprobación | Resultado |
|---|---|
| Suite completa con integración y grupo ML | 251 aprobadas en 206,07 s; incluye recuperación y fallas existentes |
| Ruff | Sin observaciones |
| Documentación y secretos | Correctos; 27 documentos, 51 IDs de requisitos/casos, 16 ADRs |
| JavaScript | Sintaxis válida con `node --check` |
| Chrome headless real | Login, pestaña Monitoreo, ocho filas de disponibilidad, dos tiendas y cuatro heartbeats; cero errores JavaScript |
| Recorrido de dos tiendas | Una ingesta aceptada, diez publicaciones confirmadas, cinco muestras por tienda, cero pendientes y cero duraciones desconocidas |
| Tiempos del recorrido reducido | T1: p95 1,725 s y p99 1,748 s. T2: p95 2,405 s y p99 2,424 s. No es el ensayo RNF-02/RNF-15 |
| API principal detenida | Minuto 17/11/2026 12:13 (UTC-03): API no disponible, cuatro heartbeats vigentes; métricas y observador continuaron respondiendo |
| Muestreo y retención | Pruebas con PostgreSQL real: un registro por minuto, consultas sin escritura, faltantes en el denominador y eliminación de muestras de más de siete días |
| Publicación y acuses perdidos | Pruebas con HTTP real: primer efecto conservado al repetir el envío, corte de cero con revisión propia y origen conservado durante revisión manual |

Estas comprobaciones corresponden a la instrumentación anterior a incorporar el PR #18.
La única advertencia de esa suite es una deprecación ya existente del cliente de pruebas de
Starlette/httpx. El recorrido de navegador usa un perfil temporal aislado. No se declara
ejecutada una campaña de 24 horas por tener el servicio implementado.

## Integración del monitoreo técnico con el PR #18

Se mantiene la pestaña accesible para todas las cuentas del TP y se documenta que corresponde
a administración de plataforma: es una simplificación del único perfil de permisos, sin RBAC.
Los recorridos de negocio siguen filtrando versiones y puntajes de ML.

La sección ML reutiliza `/health/live`, `/health`, el heartbeat de treinta segundos del entrenador
y `ml.repository.report`. El reporte y la serie por minuto incluyen versión, observaciones
incorporadas por proveedor y aprendizaje pendiente, separando proceso activo de inferencia lista.
El backend de ingesta y el modelo no se vuelven a implementar en métricas.

El ADR de métricas pasa a 0017 y su migración a 0008, después de la 0007 de ML. El puerto host
de métricas pasa a 8004 para conservar 8002 de ML. La verificación conjunta utiliza otro proyecto
de Compose y volúmenes nuevos: la base del ensayo anterior no se reinterpreta como migrada a ML.
El proyecto conjunto es `ivostock-metrics-ml-check`; conserva la vista en localhost:18000 y
usa datos sintéticos nuevos. Los contenedores del ensayo anterior quedan detenidos y sus
volúmenes conservados. El entorno de operación original y el worktree de ML siguen intactos.

| Comprobación conjunta | Resultado |
|---|---|
| Suite completa en Docker | 312 aprobadas en 257,75 s; una omitida porque la imagen no trae Node |
| Avisos, privacidad, interfaz y observador en el host con Node | 19 aprobadas; incluye la prueba omitida de avisos |
| Ruff, documentación, secretos y diferencias de Git | Correctos; 31 documentos y 17 ADRs |
| Arranque real sin historial | Proceso ML activo, entrenador activo, inferencia no lista y cero observaciones; estado persistido y mostrado en Chrome |
| Calentamiento real y corrida posterior | Diez aceptados sintéticos procesados por el entrenador y una corrida posterior decidida por ML; once incorporados, mínimo diez, cero aprendizajes pendientes |
| Monitoreo después del aprendizaje | Proceso, inferencia y entrenador activos; versión y conteo por proveedor visibles en Chrome, con cero errores JavaScript |
| Separación de responsabilidades | El muestreo reutiliza el reporte y las sondas; no genera observaciones ni ejecuta entrenamiento. Los endpoints de corridas mantienen filtrados los campos de ML |

Las fechas del tablero usan el reloj del navegador y formato explícito de 24 horas, evitando
que una preferencia regional vuelva ambigua la hora del último entrenamiento. Estas
comprobaciones demuestran instrumentación y funcionamiento del circuito reducido; no acreditan
precisión del modelo con datos reales ni los ensayos RNF-02/RNF-07/RNF-09/RNF-15.

## Estado al 19/11/2026

El último #18 se incorporó en #19 después de ejecutar Update branch en #18. La guarda vuelve
a preceder siempre al modelo, y ADR-0016 conservó su estado propuesto hasta su aceptación del 22/11/2026. En la revisión de #19
se quitó el segundo login: sólo la API principal inicia/cierra sesiones; métricas valida el
mismo token y conserva `GET /auth/me`. Una sesión revocada en la API deja de servir en métricas.

La migración `0009` agrega índices de las expresiones usadas por ventana y retención, sin
reescribir `0008` en bases existentes. Se verificaron upgrade, downgrade y nuevo upgrade en
`ivostock_indexes_test`. EXPLAIN con `enable_seqscan=off` confirmó que ambos filtros pueden usar
sus índices; esto demuestra compatibilidad de expresiones, no una mejora de rendimiento medida.

La suite completa de esta integración y los ajustes de login/índices aprobó **323 pruebas** en
Docker en 355,73 s, con una omitida por falta de Node. En el host pasaron las doce pruebas de
avisos, métricas, observador y monitoreo seleccionadas, incluida la omitida con Node.
Ruff, documentación, secretos y `git diff --check` pasaron. La corrida inicial en Windows tuvo
dos fallas preexistentes relacionadas con permisos POSIX y conversión de saltos de línea;
ambas pasaron en la suite Linux de Docker.

Los [ensayos de dos tiendas (#21)](https://github.com/ramossofia-f/TP-ISW-IvoStock/pull/21)
y [consultas (#25)](https://github.com/ramossofia-f/TP-ISW-IvoStock/pull/25) ya publican evidencia
con Celesa. **RNF-07 es la única medición pendiente.** La [preparación del laboratorio](RNF07-LABORATORIO.md)
incluye registro de una ventana inmutable y exportación con faltantes; no acredita una campaña
iniciada ni terminada. Los nuevos casos de prueba comprueban rechazo de sobrescritura,
exportación anticipada y conservación de los cortes al exportar después de reiniciar:
**tres pruebas aprobadas en Docker y en el host**, agregadas después de la suite completa.

## Pendientes históricos de la verificación inicial

Esta lista corresponde a la verificación inicial del #19; el estado actualizado es el anterior.

- RNF-07: ventana real de 24 horas, con inicio/fin explícitos y 1.440 posiciones por serie.
- RNF-02 y RNF-15: dos tiendas sanas, 1.000 vínculos por tienda, sin cola previa; recursos y
  cantidad/frecuencia de cambios declarados; p95 <30 minutos y p99 <60 minutos en cada tienda.
- RNF-09: ensayo de cinco operadores durante 30 minutos, fuera de la ventana de disponibilidad.

## Interpretación

La disponibilidad histórica procede del muestreo interno. El observador devuelve ese estado y
la accesibilidad HTTP actual; no tiene un histórico independiente. Las muestras faltantes
cuentan como no exitosas. Los workers mantienen su tolerancia de heartbeat de 660 segundos.
Los percentiles nulos indican ausencia de muestras; pendientes y duraciones desconocidas no
acreditan cumplimiento. Los datos de pruebas y sus modificaciones son sintéticos.
