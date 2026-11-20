# ADR-0004: Cola durable por vínculo en PostgreSQL

Estado: aceptado. Fecha: 25/10/2026. Alternativas desarrolladas el 18/11/2026.

## Contexto y alternativas

La API de destino admite sesenta llamadas por minuto por tienda, así que el trabajo se acumula. Si se acumulan valores vencidos de un mismo vínculo, se gasta cuota en cantidades que ya no corresponden: sólo importa el último valor de cada vínculo, sin perder su antigüedad en la fila. Se compararon tres alternativas:

- **Broker externo.** Está diseñado para colas, entrega y escalado. Pero no comparte transacción con el inventario, así que haría falta una outbox, y reemplazar el valor pendiente de un vínculo no es natural en una cola de mensajes: los valores viejos quedarían encolados y gastarían cuota. Además es otro servicio que operar y respaldar.
- **Cola en memoria del proceso.** Es la más simple y rápida. Pero se pierde si el proceso cae, lo que viola RNF-03, y no la pueden compartir varios procesos.
- **Tabla transaccional en PostgreSQL.** Una tarea por vínculo permite reemplazar el valor conservando su antigüedad, se confirma en la misma transacción que la comparación y `SKIP LOCKED` reparte el trabajo sin bloqueos. A cambio, consume por polling y suma carga a la misma base, y no escala como un broker; con dos mil vínculos y sesenta llamadas por minuto alcanza con holgura.

## Decisión

Usar tareas con clave única por vínculo, FIFO entre tareas disponibles, revisión y lease. Un reemplazo conserva antigüedad. Los eventos de comparación y sus tareas se confirman transaccionalmente. El stock deseado y los cortes permiten reconstruir trabajo. Un lock por tienda serializa envíos.

## Consecuencias

La cola comparte fallas y respaldo con el inventario. Deben comprobarse expiración de claims y respuestas atrasadas. La entrega es al menos una vez; el efecto absoluto es idempotente. Los reemplazos quedan contados y los intentos mantienen su evidencia.

## Comprobación

Pruebas de reemplazo, backoff sin bloqueo, confirmación de revisión anterior, cero persistido y cierres abruptos antes y después del HTTP. Ver [SRD](../srd/SRD.md).
