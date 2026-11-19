# Ensayo de dos tiendas (RNF-02 y RNF-15)

Generado por `scripts/ensayo_dos_tiendas.py`. Mide desde la aceptación de la corrida hasta el primer efecto externo en el simulador, por revisión, con los workers reales y la cuota de 60 llamadas por minuto y tienda. Objetivo de RNF-02: p95 menor a 30 minutos y p99 menor a 60 en cada tienda.

Ejecutado el 2026-11-18 15:02 UTC. Fuente: feed sintético del generador (10.000 SKU, semilla 7). 2 tiendas con 1000 vínculos cada una, 2000 en total.

| Corrida | Tienda | Cambios publicados | p95 (min) | p99 (min) | Pendientes | Sin duración | RNF-02 |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | T1 | 1000 | 16,0 | 17,0 | 0 | 0 | cumple |
| 1 | T2 | 1000 | 16,0 | 17,0 | 0 | 0 | cumple |
| 2 | T1 | 646 | 10,1 | 10,9 | 0 | 0 | cumple |
| 2 | T2 | 631 | 10,1 | 10,1 | 0 | 0 | cumple |

La corrida 1 lleva todos los vínculos de cero a la cantidad del proveedor: es la carga máxima. La corrida 2 sólo propaga las cantidades que el proveedor de ensayo permuta en cada consulta. Las corridas se adelantaron con `schedule-now`; en operación normal se repiten cada 300 minutos.

## Cambios por corrida

| Corrida | SKU del feed | Cambios publicados | Duración hasta drenar (min) |
|---|---:|---:|---:|
| 1 | 10000 | 2000 | 17,2 |
| 2 | 10000 | 1277 | 11,2 |

## Recursos

Darwin 25.6.0 (arm64), Docker 29.2.1 con 10 CPU y 7,7 GiB compartidos entre todos los servicios, sin límites por contenedor. Muestras de `docker stats` cada 30 segundos durante todo el ensayo; se omiten los contenedores de un solo uso (`init` y los de `docker compose run`), con menos de 3 muestras.

| Servicio | CPU promedio (%) | CPU máximo (%) | Memoria máxima (MiB) |
|---|---:|---:|---:|
| `api` | 5,4 | 29,2 | 103,3 |
| `catalog` | 1,1 | 34,5 | 72,7 |
| `compare` | 1,1 | 34,3 | 77,0 |
| `ingest` | 1,0 | 33,8 | 85,5 |
| `metrics` | 1,5 | 28,3 | 91,4 |
| `minio` | 0,5 | 1,9 | 86,4 |
| `ml` | 3,9 | 29,5 | 90,7 |
| `ml-train` | 5,7 | 50,0 | 167,0 |
| `postgres` | 2,7 | 8,1 | 81,0 |
| `provider` | 5,0 | 27,9 | 65,1 |
| `publish` | 1,7 | 34,6 | 96,1 |
| `simulator` | 4,1 | 26,7 | 94,8 |
