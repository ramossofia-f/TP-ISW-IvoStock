# ADR-0011: API de configuración sobre `services` con errores tipados

Estado: aceptado. Fecha: 10/11/2026.

## Contexto y alternativas

La interfaz de configuración (RF-25) necesita proveedores, tiendas y vínculos por HTTP. La CLI ya los resuelve en `ivostock.services`, pero esa capa lanzaba `ValueError` sin distinguir un recurso inexistente de un conflicto, y dejaba escapar `IntegrityError` (nombre de proveedor repetido, dos proveedores tomando la misma publicación a la vez) y errores de `httpx` cuyo texto puede incluir la URL. Traducirlos por el texto del mensaje sería frágil. Para evitar duplicar reglas se descartó reescribir la lógica en la API: la API sólo valida la forma de la petición y delega.

## Decisión

- Los errores de negocio son `ServiceError` y sus subclases `NotFound` (404), `Conflict` (409) y `UpstreamError` (502), todas subclases de `ValueError`, así que la CLI sigue mostrando sus mensajes. Los mensajes son fijos y nunca incluyen URLs ni texto de excepciones externas.
- `SafeRoute` envuelve cada ruta: traduce `ServiceError` a su código, un `ValueError` común a 422 y cualquier otra excepción a 500 `{"detail": "Error interno"}`. Sólo se registra el tipo y la ruta; como la excepción no llega a Starlette tampoco se imprime su traza, que podría contener SQL o credenciales. Los errores de validación 422 omiten el valor recibido (podría ser una contraseña o una URL con credenciales).
- Todo el router depende de `require_operator` a nivel de router, para que un endpoint nuevo no pueda olvidarlo.
- Recursos sin prefijo (`/providers`, `/stores`, `/links`), junto a `/auth`. La interfaz se servirá en otra ruta.
- Las acciones cuya confirmación es asíncrona (`disable`, `off`) responden 202; el resto, 200 o 201.
- La URL del proveedor no se devuelve en listados: la modificación (RF-04) la expondrá de forma deliberada.
- Incorporar una tienda sondea su existencia con una lectura de negocio antes de registrarla, porque la importación de una tienda desconocida fallaría y reintentaría indefinidamente. No usa el token administrativo del simulador.
- Los listados usan `limit` (máximo 100) y `next_offset`; la tienda con catálogo en importación rechaza sugerir y aprobar con 409 (ADR-0009).

## Consecuencias

Cada código HTTP depende de una clase, no de un texto. El sondeo de tienda consume una llamada de la cuota de esa tienda. `suggestions` sigue calculando todas las coincidencias antes de limitar la respuesta, igual que la CLI. Un `ValueError` común sigue exponiendo su mensaje, por lo que los `ValueError` nuevos en `services` deben tener texto seguro.

## Comprobación

`tests/test_api_config.py` recorre cada endpoint con PostgreSQL y el simulador reales: validación de la fuente, alerta de parseo, nombre repetido, fuente caída sin filtrar la URL, progreso de importación, segunda tienda reutilizando el inventario sin nueva corrida, rechazo de la segunda asignación activa (RF-07) incluida la carrera, paginación, apagado, reanudación y baja. También verifica que OpenAPI documenta exactamente lo implementado, sin comandos de ensayo ni de operación, que todo endpoint no público exige sesión y que los errores inesperados no filtran detalles.
