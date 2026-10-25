# ADR-0004: Cola durable por vínculo en PostgreSQL

Estado: aceptado. Fecha: 25/10/2026.

## Contexto y alternativas

La API de destino tiene capacidad limitada; acumular valores vencidos perjudica la sincronización. Se comparan broker externo, cola en memoria y tabla transaccional.

## Decisión

Usar tareas con clave única por vínculo, FIFO entre tareas disponibles, revisión y lease. Un reemplazo conserva antigüedad. Los eventos de comparación y sus tareas se confirman transaccionalmente. El stock deseado y los cortes permiten reconstruir trabajo. Un lock por tienda serializa envíos.

## Consecuencias

La cola comparte fallas y respaldo con el inventario. Deben comprobarse expiración de claims y respuestas atrasadas. La entrega es al menos una vez; el efecto absoluto es idempotente. Los reemplazos quedan contados y los intentos mantienen su evidencia.

## Comprobación

Pruebas de reemplazo, backoff sin bloqueo, confirmación de revisión anterior, cero persistido y cierres abruptos antes y después del HTTP. Ver [SRD](../srd/SRD.md).
