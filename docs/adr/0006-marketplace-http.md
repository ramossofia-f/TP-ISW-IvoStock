# ADR-0006: Marketplace simulado por HTTP

Estado: aceptado. Fecha: 25/10/2026. Alternativas desarrolladas el 18/11/2026.

## Contexto y alternativas

La demostración debe funcionar sin cuentas externas (RNF-13) y permitir provocar fallas de forma reproducible: 429, errores por publicación y credenciales revocadas. Se compararon tres alternativas:

- **Plataforma productiva.** Es el escenario real. Pero exige cuentas y credenciales externas, no permite provocar fallas a demanda, comparte cuota y datos con terceros y una prueba podría escribir stock real.
- **Dobles de prueba en memoria.** Son rápidos y deterministas para pruebas unitarias. Pero no ejercitan red, autenticación, serialización, persistencia ni la cuota, y la demostración no mostraría el circuito completo.
- **Servicio HTTP propio y persistente.** Ofrece un contrato HTTP real, con autenticación, cuota y errores controlables, sin cuentas externas, y las pruebas de integración lo usan por TCP. A cambio, hay que construirlo y mantenerlo, y lo que se demuestra vale para su contrato, no para el de un marketplace productivo.

## Decisión

Implementar un marketplace del proyecto con credenciales de prueba, catálogo preparado, cantidades absolutas, cuota y errores controlables. El catálogo se importa al incorporar la tienda; el motor sólo depende de su contrato HTTP. Un operador puede incorporar una segunda tienda desde la aplicación del MVP.

## Consecuencias

Se ejercitan red, autenticación, persistencia y errores. La evidencia acredita este contrato, no el de un marketplace productivo. Las herramientas administrativas de generación y observación se protegen con otra credencial y nunca son una vía del publicador.

## Comprobación

OpenAPI, paginación, cero y reactivación, 429 y errores por publicación. Las pruebas de integración acceden al simulador por TCP.
