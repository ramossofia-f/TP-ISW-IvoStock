# Verificación de métricas y observador

Fecha: 17/11/2026. Desarrollo aislado en la rama `feat/metricas-disponibilidad`, basada en
`1260c81`; no modifica el worktree de inferencia y monitoreo de ML.

## Alcance

Servicio interno con muestreo por minuto y retención de siete días, consultas autenticadas
compartidas con el tablero y observador HTTP sin persistencia ni alertas. Se reutilizan las
consultas operativas, sesiones y heartbeats; se agrega la información temporal que no existía
para medir publicación completa por revisión y tienda. Ver [ADR-0016](../adr/0016-metricas-y-observador.md).

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

La única advertencia de la suite es una deprecación ya existente del cliente de pruebas de
Starlette/httpx. El recorrido de navegador usa un perfil temporal aislado. No se declara
ejecutada una campaña de 24 horas por tener el servicio implementado.

## Pendiente de medir

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
