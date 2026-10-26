# Ivo Stock

Motor de sincronización de inventario desde proveedores HTTP hacia un marketplace simulado. El POC se opera por CLI y conserva snapshots, inventario, trabajo pendiente y evidencia de fallas.

El [PRD](docs/prd/PRD.md) define el producto; el [SRD](docs/srd/SRD.md), su implementación; los [ADRs](docs/adr/README.md), las decisiones; el [roadmap](docs/roadmap/ROADMAP.md), evidencia y próximos hitos.

## Arranque

Requisitos: Docker con Compose y Python 3.12. Para desarrollo local, instalar también uv 0.10.4 o compatible. El primer build requiere red y compila MinIO desde su versión fijada.

```sh
python scripts/configurar.py
docker compose up --build -d --wait
docker compose ps
```

También se puede ejecutar `make up`. La configuración inicial genera secretos aleatorios en `.env` y no sobrescribe valores existentes. Los volúmenes conservan PostgreSQL y snapshots. `docker compose down` apaga sin borrarlos.

API de infraestructura: [health](http://localhost:8000/health) y [OpenAPI](http://localhost:8000/openapi.json). Simulador: [health](http://localhost:8001/health) y [OpenAPI](http://localhost:8001/openapi.json). El POC no tiene interfaz gráfica; configuración y estado se operan desde una terminal local. La interfaz autenticada es un hito del MVP.

## Datos y configuración

Un proveedor devuelve UTF-8 por HTTP con primera fila `SKU;stock`. Por ejemplo:

```text
SKU;stock
ISBN-X;12
9780000000001;0
```

Para preparar un original real sin encabezado:

```sh
uv sync --frozen
uv run ivostock prepare "RUTA_AL_ORIGINAL" data/feeds --provenance "Celesa; snapshot real archivado" --captured-at "FECHA_DEL_ARCHIVO"
```

La salida identifica el nombre SHA-256 del derivado y su manifiesto. El original se mantiene intacto; sólo los derivados del directorio `data/feeds` se sirven por HTTP. Datos, manifiestos y `.env` quedan fuera de Git. La demo reproduce datos archivados; sus variantes de cambios y fallas son sintéticas.

El generador reproduce escenarios con semilla y guarda un manifiesto sintético junto al archivo:

```sh
uv run python -m ivostock.generador.feeds --salida data/feeds/demo.csv --skus 1000 --semilla 7
uv run python -m ivostock.generador.feeds --base data/feeds/demo.csv --salida data/feeds/truncado.csv --truncar 0.3 --semilla 7
```

También permite `--ceros`, `--corruptas` y `--deriva`, como fracciones entre cero y uno. La salida conserva el encabezado fijo `SKU;stock`; los archivos locales son entradas de preparación y generación, y los proveedores se consultan siempre por HTTP.

## Recorrido por CLI

Reemplazar `ARCHIVO.csv` por el nombre devuelto por `prepare`. Los IDs numéricos se obtienen de la salida, sin asumir que empiezan en uno. Para una demostración manual determinista, detener primero los workers; los mismos servicios se ejecutan con los comandos de un paso.

```sh
docker compose stop ingest compare publish
docker compose run --rm cli ivostock provider-add Celesa http://feeds:8080/ARCHIVO.csv
docker compose run --rm cli ivostock ingest ID_PROVEEDOR
docker compose run --rm cli ivostock seed T1 data/feeds/ARCHIVO.csv --count 1000
docker compose run --rm cli ivostock store-add T1
docker compose run --rm cli ivostock suggest ID_PROVEEDOR T1
docker compose run --rm cli ivostock approve ID_PROVEEDOR T1 --all
docker compose run --rm cli ivostock compare
docker compose run --rm cli ivostock status tasks
docker compose start ingest compare publish
```

El generador inicializa cantidades desde el feed; una vinculación coincidente no necesita escrituras. Un cambio posterior o un corte genera trabajo. `suggest ID_PROVEEDOR T1 --sku ISBN-X` busca un SKU exacto y `approve ID_PROVEEDOR T1 --items ITEM000001 ITEM000002` permite una selección. Las tiendas se preparan una sola vez y sus publicaciones permanecen estáticas.

```sh
docker compose run --rm cli ivostock off ID_VINCULO
docker compose run --rm cli ivostock provider-disable ID_PROVEEDOR
docker compose run --rm cli ivostock status links
docker compose run --rm cli ivostock status runs
docker compose run --rm cli ivostock status quarantines
docker compose run --rm cli ivostock status deadletters
docker compose run --rm cli ivostock resume ID_VINCULO
docker compose run --rm cli ivostock replay ID_CORRIDA
```

`publish` ejecuta una tarea disponible; `compare` procesa los eventos disponibles. `replay` usa el snapshot y las reglas normales, sin forzar la aceptación. `resume` utiliza el último stock deseado y conserva la falla anterior. Para ensayar un error definitivo: `ivostock fault T1 404 --item ITEM000001 --remaining 1`; se aplica a la siguiente llamada alcanzada.

La ingesta automática ocurre cada 300 minutos y no se superpone por proveedor. Los comandos manuales no cambian el próximo vencimiento. Las lecturas y escrituras comparten sesenta llamadas/minuto por tienda; reiniciar conserva el consumo.

## Pruebas

```sh
uv sync --frozen
uv run ruff check .
uv run pytest -q -m "not integration"
uv run python scripts/verificar_documentacion.py
uv run python scripts/verificar_secretos.py
docker compose --profile test run --build --rm tests
```

La integración crea y limpia exclusivamente `ivostock_test` y usa `snapshots-test`; no limpia la base de operación. Levanta un simulador propio por TCP. Incluye diez procesos terminados abruptamente en puntos reproducibles. Para correrla desde Windows o Linux con PostgreSQL y MinIO locales ya levantados: `uv run python scripts/pruebas_locales.py -q`.

El ensayo real y la interrupción del servicio PostgreSQL se ejecutan con `uv run python scripts/evaluar_poc.py --source "RUTA_AL_ORIGINAL" --captured-at "FECHA_DEL_ARCHIVO"`. Ese ensayo detiene temporalmente API y workers del proyecto, conserva los volúmenes y deja un reporte en `data/evidencia/poc.json`. Usa un proveedor y una tienda de ensayo identificados por ejecución.

El [registro de E2](docs/entregas/ENTREGA-2.md) separa resultados locales comprobados de ensayos pendientes. Las pruebas largas de disponibilidad, capacidad de interfaz y dos tiendas corresponden al MVP. ML está pendiente de definición.
