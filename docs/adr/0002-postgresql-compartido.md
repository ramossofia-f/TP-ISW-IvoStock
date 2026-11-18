# ADR-0002: PostgreSQL compartido y procesos separados

Estado: aceptado. Fecha: 25/10/2026. Alternativas desarrolladas el 18/11/2026.

## Contexto y alternativas

Configuración, inventario y trabajo necesitan commits consistentes: aceptar un inventario y registrar su evento de comparación tienen que ocurrir juntos, y el trabajo pendiente tiene que poder reconstruirse desde el estado deseado (RNF-03). Además, detener la API no debe detener el motor (RNF-08). Se compararon tres alternativas:

- **Bases por servicio con intercambio durable.** Cada proceso tiene su esquema y sus fallas quedan aisladas. A cambio, cada frontera necesita una outbox con deduplicación, la consistencia entre bases es eventual y hay que respaldar y migrar varias bases de forma coordinada: demasiada infraestructura para el tamaño del MVP.
- **Servicios que se sincronizan por llamadas HTTP.** Los contratos quedan explícitos y cada servicio se despliega por separado. Pero aceptar el inventario y encolar su trabajo quedan en dos transacciones: si el proceso cae entre ambas, el trabajo se pierde o se duplica, salvo que se agreguen reintentos e idempotencia en cada llamada. También acopla en el tiempo: si cae un servicio, se frena la cadena.
- **Una base PostgreSQL compartida por procesos separados.** Una sola transacción cubre inventario, evento y tarea, hay un único respaldo y los procesos siguen pudiendo detenerse por separado. A cambio, PostgreSQL es un punto común de falla, el esquema acopla a los procesos y escala sólo verticalmente.

## Decisión

Usar una base PostgreSQL y procesos independientes de API, ingesta, comparación y publicación. La aceptación de inventario y su evento se confirman juntos. La comparación consume eventos persistidos por polling. El simulador conserva tablas propias y el motor lo usa exclusivamente por HTTP.

## Consecuencias

Hay integridad transaccional y una sola operación de respaldo. PostgreSQL es un punto común de falla. El esquema exige coordinación mediante migraciones; detener API o workers no requiere detener los demás procesos.

## Comprobación

Detener API mientras el motor publica y consultar estado con los workers detenidos. Reiniciar PostgreSQL abruptamente conservando volumen y recuperar el trabajo. Ver [SRD](../srd/SRD.md).
