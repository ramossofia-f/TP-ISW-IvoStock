# ADR-0006: Marketplace simulado por HTTP

Estado: aceptado. Fecha: 25/10/2026.

## Contexto y alternativas

La demostración debe funcionar sin cuentas externas y permitir fallas reproducibles. Se comparan plataforma productiva, dobles de prueba en memoria y servicio HTTP persistente.

## Decisión

Implementar un marketplace del proyecto con credenciales de prueba, catálogo preparado, cantidades absolutas, cuota y errores controlables. El catálogo se importa al incorporar la tienda; el motor sólo depende de su contrato HTTP. Un operador puede incorporar una segunda tienda desde la aplicación del MVP.

## Consecuencias

Se ejercitan red, autenticación, persistencia y errores. La evidencia acredita este contrato, no el de un marketplace productivo. Las herramientas administrativas de generación y observación se protegen con otra credencial y nunca son una vía del publicador.

## Comprobación

OpenAPI, paginación, cero y reactivación, 429 y errores por publicación. Las pruebas de integración acceden al simulador por TCP.
