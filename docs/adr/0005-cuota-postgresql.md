# ADR-0005: Cuota durable por tienda

Estado: aceptado. Fecha: 25/10/2026. Alternativas desarrolladas el 18/11/2026.

## Contexto y alternativas

Lecturas y escrituras comparten sesenta llamadas por minuto por tienda, y la importación del catálogo y la publicación corren en procesos distintos. Si se exceden, el marketplace responde 429. Se compararon tres alternativas:

- **Contador en memoria.** Es simple y no agrega latencia. Pero se reinicia cuando cae el proceso, y un reinicio regalaría permisos que terminarían en 429. Tampoco lo comparten los procesos de importación y publicación.
- **Almacén adicional, por ejemplo Redis con un token bucket.** Es atómico, rápido y expira entradas solo. Pero es otro servicio que operar y respaldar, sin persistencia configurada pierde el estado al reiniciar, y la cuota quedaría separada de la identidad de tiendas y trabajo que ya está en PostgreSQL.
- **Ventana móvil en PostgreSQL con advisory lock por tienda.** Es durable, la comparten todos los procesos y vive junto a tiendas y trabajo. A cambio, cada llamada agrega una escritura y una espera por el lock de su tienda, insignificantes a sesenta llamadas por minuto, y un permiso reservado que no se llega a enviar se pierde.

## Decisión

Registrar permisos en una ventana móvil de sesenta segundos, coordinada mediante advisory lock transaccional por tienda. Cada intento reserva antes del HTTP; importación y publicación usan la misma función. El simulador aplica una ventana independiente.

## Consecuencias

Un permiso reservado y no enviado puede desperdiciarse. Reiniciar no crea permisos. La espera se persiste y los 429 se resuelven sin atribuir un fallo permanente al vínculo. Las operaciones de control del ensayo están separadas de las llamadas de negocio.

## Comprobación

Solicitudes concurrentes, mezcla de lecturas y escrituras, errores que consumen cuota, tiendas independientes y reconstrucción del cliente sin reiniciar su ventana.
