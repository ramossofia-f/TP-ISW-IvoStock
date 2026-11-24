# ADR-0003: Snapshots en almacenamiento S3

Estado: aceptado. Fecha: 25/10/2026. Alternativas desarrolladas el 18/11/2026.

## Contexto y alternativas

Cada descarga debe conservar sus bytes para reproducir la corrida y diagnosticarla. Un feed real pesa unos 3,9 MB y, con una corrida cada 300 minutos, son unos 19 MB por día y por proveedor. Se compararon tres alternativas:

- **Blobs en PostgreSQL.** El snapshot entraría en la misma transacción que la corrida y habría un solo respaldo. Pero la base crecería con datos crudos que nunca cambian, lo que encarece respaldos, vacuum y restauraciones del estado transaccional, que es chico y cambia seguido.
- **Archivos en un volumen compartido.** No agrega servicios. Pero obliga a que todos los procesos monten el mismo disco, lo que los ata a una máquina, y no ofrece escritura condicional atómica: dos procesos podrían pisar el mismo archivo. El respaldo sigue siendo aparte de la base.
- **Almacenamiento de objetos con interfaz S3.** Una clave derivada del SHA-256 con escritura condicional hace que un snapshot no pueda reemplazarse, cualquier proceso lo lee por red y la misma interfaz sirve para un proveedor cloud. A cambio, es otro servicio que operar y no comparte transacción con la base: el objeto se escribe antes del commit y puede quedar un objeto sin corrida.

## Decisión

Usar una interfaz S3 con MinIO local. Las claves se derivan del SHA-256 y la escritura condicional impide sobrescribir objetos existentes. PostgreSQL conserva referencias y resultados. Almacenar el objeto precede al commit que acepta la corrida.

## Consecuencias

Los snapshots idénticos comparten objeto y se pueden comprobar por hash. Un objeto sin corrida aceptada es tolerable; una aceptación sin snapshot no lo es. Respaldar requiere conservar base y bucket. Los snapshots reales no se incluyen en Git ni en imágenes.

## Comprobación

Recuperar los bytes originales después de reinicios, repetir una escritura con la misma clave e interrumpir entre almacenamiento y aceptación. El arranque crea el bucket de forma idempotente.
