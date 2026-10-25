# ADR-0005: Cuota durable por tienda

Estado: aceptado. Fecha: 25/10/2026.

## Contexto y alternativas

Lecturas y escrituras comparten sesenta llamadas por minuto por tienda. Un contador en memoria se reinicia al caer. Un almacén adicional permite coordinar, pero agrega otro servicio. PostgreSQL ya contiene la identidad de tiendas y trabajo.

## Decisión

Registrar permisos en una ventana móvil de sesenta segundos, coordinada mediante advisory lock transaccional por tienda. Cada intento reserva antes del HTTP; importación y publicación usan la misma función. El simulador aplica una ventana independiente.

## Consecuencias

Un permiso reservado y no enviado puede desperdiciarse. Reiniciar no crea permisos. La espera se persiste y los 429 se resuelven sin atribuir un fallo permanente al vínculo. Las operaciones de control del ensayo están separadas de las llamadas de negocio.

## Comprobación

Solicitudes concurrentes, mezcla de lecturas y escrituras, errores que consumen cuota, tiendas independientes y reconstrucción del cliente sin reiniciar su ventana.
