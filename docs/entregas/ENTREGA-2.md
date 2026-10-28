# Evidencia de la Entrega 2

Ejecución local: 25/10/2026. El alcance está en el [PRD](../prd/PRD.md), los protocolos en el [SRD](../srd/SRD.md) y los comandos en el [README](../../README.md).

## Entorno

Windows con Docker Desktop y contenedores Linux. Docker dispone de 8 CPU y 8.174.735.360 bytes de RAM compartidos, sin asignación dedicada por servicio. PostgreSQL 15, MinIO construido desde su etiqueta fijada y Python 3.12. Las versiones de bibliotecas están en `uv.lock`.

## Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Pruebas unitarias e integración dentro de Docker | 68 aprobadas en 50,46 s |
| Cierres abruptos de procesos en puntos reproducibles | Diez escenarios aprobados, incluidos HTTP aceptado antes de confirmar y corte persistido |
| Confirmación atrasada frente a un corte nuevo | La revisión de cero se conserva y termina aplicada |
| Fallo definitivo de un corte | Permanece en falla; reanudar aplica cero y conserva la dead letter |
| Cuota compartida y persistente | Concurrencia, lectura/escritura, errores, 429 y reinicio del cliente aprobados |
| Build y arranque completo | Imágenes construidas; servicios con health checks saludables |
| Feed real archivado | 4.132.470 bytes originales; 255.289 filas; 255.129 SKU; cero errores de parseo |
| Preparación | Diez bytes de cabecera agregados; original intacto y hashes registrados |
| Ingesta completa y comparación inicial | 7,047 s, con fuente HTTP y snapshots en MinIO |
| Propagación con API detenida | Confirmada en el simulador mediante observador de control |
| Corrida repetida estable | Cero escrituras adicionales |
| Corrida truncada | Cuarentena sin propagarla |
| Dead letter y revisión | Error 404 conservado y reanudación confirmada |
| Recuperación automática de proceso | Contenedor de ensayo reiniciado una vez; actividad comprobada en 5,922 s |
| PostgreSQL terminado con SIGKILL | Recuperación y drenado de cortes en 5,687 s, conservando volumen |
| Conservación tras caída de base | Diez cortes confirmados en cero; cero trabajo vigente perdido |
| Análisis estático, documentación y secretos | Aprobados; 17 documentos, 51 IDs de requisitos/casos y ocho ADRs |

El ensayo real preparó un catálogo de 1.000 publicaciones y vinculó diez. Las variantes de cantidad, truncamiento y falla son sintéticas y se identifican como tales. El origen es un snapshot archivado de Celesa con fecha de archivo 20/09/2026; no se presenta como lectura en vivo. El reporte reproducible y sus hashes están en `data/evidencia/poc.json`, fuera de Git.

Estas mediciones corresponden al POC. No acreditan los ensayos del MVP de dos tiendas y 2.000 vínculos, cinco operadores o disponibilidad funcional durante veinticuatro horas.

## Recorrido de demostración

Ejecución local: 26/10/2026, sobre el recorrido del video (sesión de usuario, catálogo en segundo plano, proveedor con variantes, caídas, fallas transitorias y monitor).

### Entorno

macOS 26.6.2 (Apple M4) con Docker Desktop 29.2.1 y contenedores Linux aarch64. Docker dispone de 10 CPU y 8.217.059.328 bytes de RAM compartidos, sin asignación dedicada por servicio. Mismas imágenes y versiones que el entorno anterior.

### Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Pruebas unitarias e integración dentro de Docker | 79 aprobadas en 31,80 s. Suma reanudación del catálogo tras matar su worker, aprobación previa a la primera ingesta, baja de proveedor (RF-20), fuente inaccesible (RF-23) y credencial revocada (RF-24) |
| Análisis estático, documentación y secretos | Aprobados; 17 documentos, 51 IDs de requisitos/casos y nueve ADRs |
| Arranque completo | Nueve servicios saludables, incluidos `catalog` y `provider` |
| Login de demostración | Comandos rechazados sin sesión; `Admin`/`Admin` autenticado |
| Alta de tienda | Muestra de 127.564 publicaciones (50 % de 255.129 SKU distintos) con stock cero; el alta devuelve el control y la importación sigue en segundo plano |
| Cuota durante la importación | Máximo observado de 60 llamadas en 60 segundos según el cliente y según el simulador. La ventana móvil admite ráfagas: se observaron 59 páginas en unos 5 segundos y luego la espera hasta liberar cupo |
| SIGKILL del worker de catálogo | Reanudó desde la última página confirmada (29.700 y luego 53.500 publicaciones); sin locks retenidos tras la caída |
| SIGKILL de PostgreSQL durante la importación | Caída de unos 8 segundos y recuperación automática del WAL; el worker registró `OperationalError` y retomó solo, desde 29.700, sin reiniciarlo |
| Catálogo completo | 127.564 de 127.564 publicaciones, sin duplicados; máximo de 60 llamadas en 60 segundos durante toda la importación |
| Alta del proveedor | 255.129 SKU validados por `http://provider:8081/celesa.csv`, 0 % de errores de parseo, 127.564 coincidencias con T1 y primera ingesta programada a 300 minutos |
| Aprobación antes de la primera ingesta | 3.600 vínculos en `awaiting_ingest`, todos con confirmado cero y sin tareas encoladas |
| Primera ingesta con `schedule-now` | Corrida aceptada por el worker de ingesta y 3.600 tareas encoladas por el comparador |
| Fallas transitorias provocadas | Vínculo 1: 429 y aplicado (200) 1,0 s después. Vínculo 2: 503, 503 a los 35 s y aplicado (200) 24 s después, con backoff |
| Propagación completa | 3.600 sincronizados, 3.600 con confirmado positivo y distinto del inicial, cero pendientes, cero fallas y cero dead letters. 3.600 escrituras aplicadas en unos 59 minutos efectivos, a 60 por minuto |
| 429 del simulador | Además del provocado, el simulador respondió 4 veces 429 en unas 4.900 llamadas, porque su ventana y la del cliente no coinciden al milisegundo. Se esperó `Retry-After` sin gastar reintentos ni crear dead letters |
| Suspensión del equipo | El equipo se suspendió unos 8 minutos durante la publicación; al reanudar, los workers siguieron sin pérdida de trabajo ni exceso de cuota |

## Preparación de entrega

La implementación, las pruebas y la documentación están verificadas localmente y en la CI remota, que pasó en `main`. El video de la demostración está publicado en https://youtu.be/4_mCiduyV24; muestra el recorrido registrado en esta página, grabado con comandos reales sobre el sistema local. El [roadmap](../roadmap/ROADMAP.md) contiene la tabla de cierre y el guion.
