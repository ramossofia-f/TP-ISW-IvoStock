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

## Preparación de entrega

La implementación, las pruebas y la documentación están verificadas localmente y organizadas en commits con las coautorías del equipo. Quedan pendientes el push, la grabación/publicación del video de 5–12 minutos y la comprobación de CI remoto. El [roadmap](../roadmap/ROADMAP.md) contiene la tabla de cierre y el guion.
