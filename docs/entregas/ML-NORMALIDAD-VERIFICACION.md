# Verificación del detector global de normalidad

Fecha: 17/11/2026. Rama local `feat/ml-inferencia-monitoreo`, base `1260c81`.
Comprobación de los cambios del worktree antes de crear un commit o ejecutar CI remoto.
Diseño: [ADR-0016](../adr/0016-normalidad-global-y-aprendizaje-durable.md).

## Entorno y aislamiento

Windows, Docker Desktop 29.2.1 con contenedores Linux; PostgreSQL 15 y MinIO propios del proyecto
Compose `ivostock-ml-check`. Se eliminaron publicaciones de puertos mediante un override local,
sin usar contenedores, bases ni volúmenes de los proyectos de demostración o disponibilidad.
Las pruebas crean/limpian exclusivamente `ivostock_test` y `snapshots-test` dentro de ese proyecto.
Python 3.12.15 en imagen; dependencias de `uv.lock`, sklearn 1.9.1 y numpy 2.5.4 sólo en la imagen
de entrenamiento/pruebas. La imagen de inferencia no incorpora esas dependencias.

## Resultados

| Comprobación ejecutada | Resultado |
|---|---|
| Suite completa en Docker, `docker compose --profile test run --build --rm tests` con el proyecto/override anteriores | 286 aprobadas, una omitida, en 306,98 s |
| Pruebas adicionales de privacidad de `usuario>` en imagen `ml-train` | Tres aprobadas en 0,86 s; los comandos de usuario no muestran métricas privadas ni ofrecen `ml-report`/`ml-reproduce` |
| JavaScript real con Node.js en el host (`tests/ml/notice_harness.cjs`) | Aviso con proveedor/corrida, contenido tratado como texto, limpieza tras aceptación/baja y respuesta tardía después de logout comprobados |
| Ruff, enlaces/IDs documentales y secretos | Aprobados |
| `node --check src/ivostock/static/app.js` y `git diff --check` | Aprobados |
| Construcción y arranque real con `up -d --build --wait ml ml-train` | Ambos servicios saludables sin historial |
| Sondas reales después de ese arranque | `/health/live`: 200; `/health`: 503 (calentamiento); `/health/training`: 200 |

La prueba omitida en Docker es la del comportamiento del aviso: esa imagen no instala Node.js.
Se ejecutó correctamente en el host. En total se aprobaron 289 pruebas Python en contenedores
entre la suite y las tres pruebas adicionales. El único warning de la suite fue la deprecación
del transporte de `TestClient` de una dependencia.

La suite comprueba por TCP y con PostgreSQL/S3 reales:

- Feed sano aceptado con la versión anterior, publicación antes de entrenar y aprendizaje posterior.
- Feed anómalo que pasaría las reglas: cuarentena sin inventario nuevo, evento, tareas ni observación.
- Tres aceptaciones y propagaciones con ML detenido; pendientes conservados, recuperación y procesamiento único.
- Proveedor nuevo por respaldo hasta incorporar sus diez observaciones, sin crear otro modelo.
- Error de entrenamiento, conservación de la versión previa, espera y recuperación del pendiente.
- Unicidad de observación, inmutabilidad de versiones, reproducción sin activación y privacidad de la API.
- Cuatro cierres abruptos del entrenador: tarea tomada, modelo calculado, publicación sin commit y publicación confirmada.
- Cierre durante aceptación/outbox: ambos trabajos se revierten y la siguiente corrida recupera el circuito.
- Contrato de archivo inválido sin aprendizaje y retiro del aviso tras aceptación o baja.

Las pruebas unitarias comprueban también la coincidencia del RBF exportado con sklearn,
ponderación temporal, ventana por proveedor, autenticación del servicio y plazo total de un
segundo sin reintentar inferencia.

## Evaluación y límites

El [ensayo sintético reservado](ML-NORMALIDAD-EVALUACION.md) se generó con
`uv run --group ml python scripts/ml_evaluar_normalidad.py`: 81 % de detección de truncamientos
leves y 8 % de falsas cuarentenas en el escenario estable, con la configuración inicial.
Rechaza también las novedades legítimas masivas no observadas en entrenamiento. No se ajustaron
parámetros para ocultar estos resultados ni se atribuye al modelo nuevo la evaluación binaria anterior.

En el host Windows, la suite sin integración aprobó 131 pruebas y encontró dos fallas ya existentes:
la expectativa de permisos POSIX 0600 y la comparación LF frente a CRLF. Ambas pasan en Docker.
Tres pruebas nuevas de privacidad y la del aviso también pasaron en el host.

No se ejecutó CI remoto para estos cambios, una ventana de uptime de 24 horas ni una evaluación
del nuevo modelo con incidentes reales etiquetados. El aviso se comprobó ejecutando su JavaScript
con un DOM de prueba; no se hizo una inspección visual en navegador. El calentamiento se probó
por disparos controlados; no se esperaron diez intervalos automáticos de cinco horas.

La [demostración del décimo aceptado](ENTREGA-3-ML-PENDIENTES.md) queda pendiente para el video
de la Entrega 3. La publicación asíncrona de esa versión debe observarse antes de mostrar ML decidiendo.
