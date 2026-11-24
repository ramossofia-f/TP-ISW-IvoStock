# Ensayo de dos tiendas (RNF-02 y RNF-15)

Generado por `scripts/ensayo_dos_tiendas.py`. Mide desde la aceptación de la corrida hasta el primer efecto externo en el simulador, por revisión, con los workers reales y la cuota de 60 llamadas por minuto y tienda. Objetivo de RNF-02: p95 menor a 30 minutos y p99 menor a 60 en cada tienda.

Ejecutado el 2026-11-19 01:27 UTC. Fuente: inventario real (celesa.csv, SHA-256 `fb68d3ef33a8`). 2 tiendas con 1000 vínculos cada una, 2000 en total.

| Corrida | Tienda | Cambios publicados | p95 (min) | p99 (min) | Pendientes | Sin duración | RNF-02 |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | T1 | 1000 | 15,1 | 16,1 | 0 | 0 | cumple |
| 1 | T2 | 1000 | 16,0 | 16,2 | 0 | 0 | cumple |
| 2 | T1 | 555 | 9,0 | 9,1 | 0 | 0 | cumple |
| 2 | T2 | 569 | 9,1 | 10,0 | 0 | 0 | cumple |

La corrida 1 lleva todos los vínculos de cero a la cantidad del proveedor: es la carga máxima. La corrida 2 sólo propaga las cantidades que el proveedor de ensayo permuta en cada consulta. Las corridas se adelantaron con `schedule-now`; en operación normal se repiten cada 300 minutos.

## Cambios por corrida

| Corrida | SKU del feed | Cambios publicados | Duración hasta drenar (min) |
|---|---:|---:|---:|
| 1 | 255129 | 2000 | 16,2 |
| 2 | 255129 | 1124 | 10,2 |

## Recursos

Darwin 25.6.0 (arm64), Docker 29.2.1 con 10 CPU y 7,7 GiB compartidos entre todos los servicios, sin límites por contenedor. Muestras de `docker stats` cada 30 segundos durante todo el ensayo; se omiten los contenedores de un solo uso (`init` y los de `docker compose run`), con menos de 3 muestras.

| Servicio | CPU promedio (%) | CPU máximo (%) | Memoria máxima (MiB) |
|---|---:|---:|---:|
| `api` | 4,3 | 29,4 | 108,5 |
| `catalog` | 3,0 | 69,9 | 94,0 |
| `compare` | 2,4 | 61,6 | 65,1 |
| `ingest` | 2,8 | 61,3 | 104,5 |
| `metrics` | 0,7 | 19,6 | 91,6 |
| `minio` | 0,5 | 2,7 | 146,9 |
| `ml` | 4,2 | 26,9 | 94,4 |
| `ml-train` | 4,9 | 47,5 | 173,1 |
| `postgres` | 3,4 | 53,8 | 249,3 |
| `provider` | 4,8 | 24,6 | 80,3 |
| `publish` | 3,0 | 62,7 | 118,6 |
| `simulator` | 4,4 | 25,9 | 108,7 |
