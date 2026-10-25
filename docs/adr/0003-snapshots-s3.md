# ADR-0003: Snapshots en almacenamiento S3

Estado: aceptado. Fecha: 25/10/2026.

## Contexto y alternativas

Cada descarga debe conservar sus bytes para reproducción y diagnóstico. Las opciones son blobs en PostgreSQL, archivos en un volumen compartido o almacenamiento de objetos.

## Decisión

Usar una interfaz S3 con MinIO local. Las claves se derivan del SHA-256 y la escritura condicional impide sobrescribir objetos existentes. PostgreSQL conserva referencias y resultados. Almacenar el objeto precede al commit que acepta la corrida.

## Consecuencias

Los snapshots idénticos comparten objeto y se pueden comprobar por hash. Un objeto sin corrida aceptada es tolerable; una aceptación sin snapshot no lo es. Respaldar requiere conservar base y bucket. Los snapshots reales no se incluyen en Git ni en imágenes.

## Comprobación

Recuperar los bytes originales después de reinicios, repetir una escritura con la misma clave e interrumpir entre almacenamiento y aceptación. El arranque crea el bucket de forma idempotente.
