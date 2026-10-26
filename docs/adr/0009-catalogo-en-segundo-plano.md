# ADR-0009: Importación de catálogo en segundo plano con punto de control

Estado: aceptado. Fecha: 26/10/2026.

## Contexto y alternativas

Una tienda de demostración tiene 127.564 publicaciones. A cien por página y sesenta llamadas por minuto, leerla lleva más de veinte minutos. Se compararon tres alternativas:

- **Importación sincrónica en la CLI.** Es la más simple, pero bloquea al usuario y, si el proceso cae, se pierde el avance o se repite toda la lectura gastando cuota.
- **Importación en el worker de publicación.** Reutiliza un proceso, pero mezcla dos responsabilidades: una tienda importando competiría con la publicación de otras y una falla de una afectaría a la otra.
- **Worker de catálogo con punto de control en PostgreSQL.** Agrega un proceso, pero el alta devuelve el control enseguida y el avance sobrevive a la caída del worker o de la base.

## Decisión

El alta registra la tienda en estado `importing`. El worker `catalog` importa una página por ciclo con la misma cuota y el mismo cliente HTTP que la publicación. Las publicaciones de cada página y el nuevo `import_offset` se confirman en una sola transacción. El lock de sesión por tienda evita dos importaciones simultáneas. `store-add --wait` ejecuta la misma función en el proceso de la CLI para recorridos manuales y pruebas.

## Consecuencias

Una página recibida pero no confirmada se vuelve a pedir: puede gastar una llamada extra, pero `ON CONFLICT DO NOTHING` impide duplicar publicaciones. El progreso (`processed`, `total`) es consultable con `status stores` y `monitor`. Un 429 respeta `Retry-After`; un 5xx o una caída de PostgreSQL se reintentan; 401 y 403 degradan la tienda. Vincular exige el catálogo completo.

## Comprobación

Prueba de integración que mata el worker después de confirmar la primera página y verifica que reanuda desde la página 2 sin duplicados. El recorrido de demostración mata además el worker y PostgreSQL durante la importación real.
