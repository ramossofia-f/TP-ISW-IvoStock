# Ensayo de consultas (RNF-09)

Generado por `scripts/ensayo_consultas.py`. Cinco operadores autenticados hacen una consulta por segundo cada uno durante 30 minutos, con carga abierta: cada consulta sale en su segundo programado y la latencia se mide desde ese instante, en el cliente. Objetivo de RNF-09: p95 menor a 2 segundos.

Ejecutado el 2026-11-19 02:56 UTC sobre 2000 vínculos (inventario real de Celesa). **Resultado: cumple.**

| Consulta | Cantidad | Errores | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|---:|
| `GET /links` de una tienda, cien vínculos desde un offset al azar | 4500 | 0 | 16 | 19 | 20 | 82 |
| `GET /providers/{id}/suggestions` con un SKU vinculado | 2250 | 0 | 14 | 16 | 18 | 31 |
| `GET /runs`, las veinte corridas más recientes | 1125 | 0 | 13 | 15 | 16 | 56 |
| `GET /links/summary` de una tienda: pendientes, fallidos y sincronizados | 1125 | 0 | 16 | 18 | 20 | 28 |
| **Total** | 9000 | 0 | 15 | 18 | 20 | 82 |

## Motor durante el ensayo

Se adelantó una ingesta al empezar y otra a la mitad, para que la comparación y la publicación compitan con las consultas. Corridas: #5 accepted, #6 accepted. Publicaciones aplicadas durante la medición: 2835.

## Recursos

Darwin 25.6.0 (arm64), Docker 29.2.1 con 10 CPU y 7,7 GiB compartidos entre todos los servicios, sin límites por contenedor. Muestras de `docker stats` cada 30 segundos durante todo el ensayo; se omiten los contenedores de un solo uso (`init` y los de `docker compose run`), con menos de 3 muestras.

| Servicio | CPU promedio (%) | CPU máximo (%) | Memoria máxima (MiB) |
|---|---:|---:|---:|
| `api` | 5,5 | 24,4 | 105,1 |
| `catalog` | 1,4 | 53,5 | 111,2 |
| `compare` | 1,4 | 52,9 | 81,2 |
| `ingest` | 2,4 | 57,1 | 178,4 |
| `metrics` | 1,0 | 19,6 | 91,7 |
| `minio` | 0,4 | 1,7 | 165,4 |
| `ml` | 4,3 | 21,6 | 91,5 |
| `ml-train` | 6,7 | 47,2 | 183,2 |
| `postgres` | 4,7 | 99,8 | 257,4 |
| `provider` | 3,9 | 21,2 | 77,9 |
| `publish` | 2,1 | 53,1 | 116,1 |
| `simulator` | 4,5 | 21,8 | 106,9 |
