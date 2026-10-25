# ADR-0002: PostgreSQL compartido y procesos separados

Estado: aceptado. Fecha: 25/10/2026.

## Contexto y alternativas

Configuración, inventario y trabajo necesitan commits consistentes. Se comparan una base compartida, bases por servicio con intercambio durable y servicios sincronizados por llamadas HTTP.

## Decisión

Usar una base PostgreSQL y procesos independientes de API, ingesta, comparación y publicación. La aceptación de inventario y su evento se confirman juntos. La comparación consume eventos persistidos por polling. El simulador conserva tablas propias y el motor lo usa exclusivamente por HTTP.

## Consecuencias

Hay integridad transaccional y una sola operación de respaldo. PostgreSQL es un punto común de falla. El esquema exige coordinación mediante migraciones; detener API o workers no requiere detener los demás procesos.

## Comprobación

Detener API mientras el motor publica y consultar estado con los workers detenidos. Reiniciar PostgreSQL abruptamente conservando volumen y recuperar el trabajo. Ver [SRD](../srd/SRD.md).
