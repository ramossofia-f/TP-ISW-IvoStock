# RNF-07: resultado de la campaña del laboratorio

Ejecución de 24 horas de reloj terminada y evidencia exportada. API y motor cumplen el umbral del 99 %.

Ventana UTC: `2026-11-19T23:40:00+00:00` a `2026-11-20T23:40:00+00:00` (fin exclusivo).
Ventana Buenos Aires: `2026-11-19T20:40:00-03:00` a `2026-11-20T20:40:00-03:00`.
Exportación UTC: `2026-11-20T23:41:04.080636+00:00`.
Revisión medida: `7600ae55c34d9a0ffef1728d2f9dfcb723c6adb0`; base `origin/feat/metricas-disponibilidad`, con #18 incorporado antes de #19.
Acceso: `labs004.udesa.edu.ar`; equipo físico: `labo-s004-20`.

Entorno: Ubuntu 24.04.4 LTS, kernel `7.0.0-43-generic`, x86_64; Intel(R) Core(TM) i7-14700K, 28 CPU lógicas y 31.08 GiB de RAM del host. Recursos compartidos, sin reserva exclusiva ni límites adicionales en los contenedores.
Docker 29.8.1; Compose 5.5.1. Proyecto `rnf07_fortega_20261119`.
Antes de medir se verificaron las políticas `unless-stopped`, Docker habilitado al arrancar y la recuperación de datos tras recrear los contenedores. PostgreSQL y MinIO usan volúmenes con nombre; el directorio de trabajo está en `/scratch`, sobre ext4.

Carga sintética declarada: generador con semilla 7, 2000 SKU y cantidades positivas de 1 a 50. No se encontró el archivo archivado de Celesa en los directorios revisados. T1 y T2 tienen 1.000 publicaciones y 1.000 vínculos aprobados cada una; comparten 500 SKU. El proveedor de ensayo permuta las cantidades positivas del 40 % de los SKU en cada descarga. Las ingestas automáticas conservan su intervalo normal de 300 minutos. La preparación y el drenaje terminaron antes de la ventana.

Muestras esperadas: **1440**; registradas: **1440**; faltantes: **0**.

| Componente | Muestras exitosas / esperadas | Disponibilidad | Umbral 99 % |
|---|---:|---:|---|
| API | 1440 / 1440 | 100.000000 % | Cumple |
| Motor | 1440 / 1440 | 100.000000 % | Cumple |

El apagado previsto se declaró de 07:00 a 08:00 de Buenos Aires. La configuración local también registra un reinicio de lunes a viernes a las 07:30, con hasta 120 segundos de demora. Los intervalos siguientes provienen de las posiciones reales de la serie; el corte de SSH por sí solo no genera muestras faltantes.

Posiciones sin muestra: 0 minutos.


API: posiciones no exitosas: 0 minutos.


Motor: posiciones no exitosas: 0 minutos.


Comprobación al exportar: cambio de ID de arranque del host: sí; identidad y fecha de creación de ambos volúmenes conservadas: sí; servicios persistentes disponibles: sí; configuración y feed base intactos: sí.

Todos los faltantes permanecen en el denominador como no exitosos. Se conservó la ventana original: sin descontar cortes, extender el final ni rellenar posiciones. El motor mantiene la tolerancia de heartbeat de 660 segundos del ADR-0017.

La ejecución terminada y el cumplimiento del requisito se informan por separado. Esta es disponibilidad interna según #19; no demuestra una sonda funcional externa ni un observador independiente disponible durante los cortes. No sustituye los ensayos de capacidad de #21 y #25.

Los archivos crudos `data/evidencia/rnf07-campana.json` y `data/evidencia/rnf07-campana-resultado.json`, la procedencia sintética y el entorno permanecen fuera de Git junto con `.env` y los datos. Los dos volúmenes se conservan.

SHA-256 del archivo de campaña: `9c2f9c4a1a75fa108e2ba42a4d6a733b20e828ad7225537ae61a94ed04769ff2`.
SHA-256 de la evidencia exportada: `146c4b814d11e843e934d1b77b7ed2309768e0678c47cd273a9dc88c2415eb5b`.

Durante la ventana se ejecutó una ingesta manual del proveedor sintético (corrida 5, 2026-11-20T13:09:25.794974-03:00). Se aceptaron 2000 SKU y se conservó la programación de ingestas automáticas.
