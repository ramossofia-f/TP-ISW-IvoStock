# RNF-07: reporte con mantenimiento programado excluido

Ejecución finalizada y evidencia exportada. El porcentaje de este reporte utiliza la exclusión solicitada por el usuario.

Ventana de reloj UTC: `2026-11-19T23:40:00+00:00` a `2026-11-20T23:40:00+00:00` (fin exclusivo).
Ventana Buenos Aires: `2026-11-19T20:40:00-03:00` a `2026-11-20T20:40:00-03:00`.
Cambio de criterio registrado en UTC: `2026-11-19T23:55:46.909853+00:00`, antes del corte excluido.

Exclusión: `2026-11-20T07:00:00-03:00` a `2026-11-20T08:00:00-03:00` (fin exclusivo), Desconexion o mantenimiento programado declarado por el usuario.

Tiempo considerado: **23 horas**, **1380 minutos esperados**. Se excluyen 60 minutos de mantenimiento; el cierre original se conserva.
Muestras registradas: **1380**; faltantes fuera del mantenimiento: **0**.

| Componente | Muestras exitosas / consideradas | Disponibilidad | Umbral 99 % ajustado |
|---|---:|---:|---|
| API | 1380 / 1380 | 100.000000 % | Cumple |
| Motor | 1380 / 1380 | 100.000000 % | Cumple |

Estos porcentajes corresponden al protocolo modificado de 23 horas consideradas. La evaluación original de las 24 horas completas, incluidos todos los cortes, se conserva aparte en `RNF07-RESULTADO-COMPLETO-20261119.md` y en el JSON original. Este reporte ajustado no acredita por sí solo el requisito original de 24 horas completas.

Revisión: `7600ae55c34d9a0ffef1728d2f9dfcb723c6adb0`; entrada SSH: `labs004.udesa.edu.ar`; equipo físico: `labo-s004-20`.
Entorno: Ubuntu 24.04.4 LTS, kernel `7.0.0-43-generic`, Intel(R) Core(TM) i7-14700K, 28 CPU lógicas y 31.08 GiB de RAM compartida. Docker 29.8.1; Compose 5.5.1.
Carga sintética: 2.000 SKU, semilla 7, cantidades positivas de 1 a 50; T1 y T2 con 1.000 vínculos cada una. El proveedor de ensayo permuta el 40 % de las cantidades positivas y las ingestas conservan el intervalo normal de 300 minutos. La preparación y el drenaje terminaron antes de iniciar la ventana.

Posiciones faltantes fuera del mantenimiento: 0 minutos.


API: posiciones no exitosas fuera del mantenimiento: 0 minutos.


Motor: posiciones no exitosas fuera del mantenimiento: 0 minutos.


Fuera de la exclusión, cada posición faltante cuenta como no exitosa. Se conserva la tolerancia del motor de 660 segundos. La finalización de la ejecución y el cumplimiento del umbral se informan por separado.

Comprobación al exportar: volúmenes conservados: sí; servicios persistentes disponibles: sí.

La disponibilidad procede del muestreo interno; no acredita una sonda funcional externa ni un observador independiente durante el corte. Los datos crudos y las credenciales permanecen fuera de Git; los dos volúmenes se conservan.

SHA-256 del resultado original: `146c4b814d11e843e934d1b77b7ed2309768e0678c47cd273a9dc88c2415eb5b`.
SHA-256 de la configuración de exclusión: `225b099c1658980d4ff6d17b75d5f796e3c6722807538f767acfadc54620f31d`.

Durante la ventana se ejecutó una ingesta manual del proveedor sintético (corrida 5, 2026-11-20T13:09:25.794974-03:00). Se aceptaron 2000 SKU y se conservó la programación de ingestas automáticas.
