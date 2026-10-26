# Ivo Stock

TP integrador, Ingeniería de Software.

**Grupo:**

- Sofía Ramos (https://github.com/ramossofia-f)
- María Saráchaga (https://github.com/mariasarachaga)
- Francisco Ortega (https://github.com/fortega00)

## Entregas

| Entrega | Contenido | Video |
|---|---|---|
| 1. Diseño (20/09/2026, aprobada) | PRD, roadmap y ADRs entregados en el commit [`354b155`](https://github.com/ramossofia-f/TP-ISW-IvoStock/tree/354b155) | https://www.youtube.com/watch?v=zP0HYAmsSoY |
| 2. POC y SRD (27/10/2026) | [PRD](docs/prd/PRD.md) revisado con la devolución, [SRD](docs/srd/SRD.md), [ADRs](docs/adr/README.md), [roadmap](docs/roadmap/ROADMAP.md), [evidencia](docs/entregas/ENTREGA-2.md) y el POC descripto abajo | Pendiente |

La devolución de la Entrega 1 está incorporada: disponibilidad verificable (RNF-07), criterios de aceptación con K = 2 y forma de verificación, supuestos con plan B, script de medición del feed, infraestructura justificada en los ADRs y documentos en español. Para responder a la observación de alcance excesivo, el MVP se redujo a 2.000 vínculos en dos tiendas y cinco operadores.

Motor de sincronización de inventario desde proveedores HTTP hacia un marketplace simulado. El POC se opera por CLI y conserva snapshots, inventario, trabajo pendiente y evidencia de fallas.

El [PRD](docs/prd/PRD.md) define el producto; el [SRD](docs/srd/SRD.md), su implementación; los [ADRs](docs/adr/README.md), las decisiones; el [roadmap](docs/roadmap/ROADMAP.md), evidencia y próximos hitos.

## Arranque

Requisitos: Docker con Compose y Python 3.12. Para desarrollo local, instalar también uv 0.10.4 o compatible. El primer build requiere red y compila MinIO desde su versión fijada.

```sh
python scripts/configurar.py
docker compose up --build -d --wait
docker compose ps
```

También se puede ejecutar `make up`. La configuración inicial genera secretos aleatorios en `.env`, agrega las claves que falten y no sobrescribe valores existentes. Los volúmenes conservan PostgreSQL y snapshots. `docker compose down` apaga sin borrarlos; para empezar de cero sin perder una corrida anterior, usar otro `COMPOSE_PROJECT_NAME`. Si el puerto 5432 ya está ocupado por un PostgreSQL local, definir `POSTGRES_HOST_PORT=5433` en `.env`.

| Servicio | Función |
|---|---|
| `postgres`, `minio` | Estado, cola y cuota; snapshots inmutables |
| `api` | [health](http://localhost:8000/health) y [OpenAPI](http://localhost:8000/openapi.json) |
| `simulator` | Marketplace simulado: [health](http://localhost:8001/health) y [OpenAPI](http://localhost:8001/openapi.json) |
| `provider` | Proveedor de ensayo en `http://localhost:8081/ARCHIVO.csv` (`http://provider:8081` dentro de Docker) |
| `ingest`, `compare`, `publish`, `catalog` | Workers independientes: ingesta, comparación, publicación e importación de catálogo |
| `user`, `cli` | Perfil `tools`: sesión de usuario y CLI de backend, con `docker compose run --rm` |

El POC no tiene interfaz gráfica; configuración y estado se operan desde una terminal local. La interfaz autenticada es un hito del MVP.

## Simplificaciones del POC

- **Marketplace simulado.** Las tiendas son un servicio HTTP propio con cuota de 60 llamadas/minuto y errores provocables. No hay OAuth: las credenciales están preconfiguradas por entorno. Un funcionamiento correcto contra el simulador no acredita la integración productiva.
- **Catálogo sintético.** Las publicaciones se generan con SKU tomados del feed real; sus atributos no son reales y permanecen estáticos.
- **Fuente real archivada.** Celesa se reproduce desde un snapshot archivado y servido localmente por HTTP, no desde el endpoint vivo. Las variantes de cambios y fallas son sintéticas y se identifican como tales.
- **Login de demostración.** La sesión `usuario>` imita al futuro frontend y valida localmente la cuenta `Admin`/`Admin` contra un hash PBKDF2 en `.env`. No hay API de login (`POST /auth/login`), cuentas individuales ni interfaz gráfica: corresponden al MVP (RF-01, RF-25). La API sólo expone `GET /health`.
- **Tienda generada al darla de alta.** `store-add` le pide al simulador una tienda con el 50 % de los SKU distintos del inventario configurado (`CATALOG_FEED`), todas con stock cero. En producción la tienda ya existiría.
- **Proveedor con variantes.** El servicio `provider` reproduce el archivo archivado y, en cada consulta, permuta las cantidades positivas del 40 % de los SKU. `?no-changes=true` devuelve el archivo intacto.
- **Una tienda y un proveedor.** La segunda tienda y las mediciones de escala, consulta y disponibilidad son del MVP.
- **Sin ML.** El componente se define e implementa para la Entrega 3.

## Datos y configuración

Un proveedor devuelve UTF-8 por HTTP con primera fila `SKU;stock`. Por ejemplo:

```text
SKU;stock
ISBN-X;12
9780000000001;0
```

La demostración usa el inventario preparado de Celesa como `data/feeds/celesa.csv` (con encabezado). Para preparar un original real sin encabezado:

```sh
uv sync --frozen
uv run ivostock prepare "RUTA_AL_ORIGINAL" data/feeds --provenance "Celesa; snapshot real archivado" --captured-at "FECHA_DEL_ARCHIVO"
```

Para reproducir la caracterización del feed que figura en el PRD: `uv run python scripts/analizar_feed.py data/feeds/ARCHIVO.csv`. Usa el mismo parser del motor y, con dos archivos, calcula además `D`, `Z`, `p` y la cantidad de diferencias.

La salida de `prepare` identifica el nombre SHA-256 del derivado y su manifiesto; para la demostración se copia como `data/feeds/celesa.csv`. El original se mantiene intacto; sólo los derivados del directorio `data/feeds` se sirven por HTTP. Datos, manifiestos y `.env` quedan fuera de Git. La demo reproduce datos archivados; sus variantes de cambios y fallas son sintéticas.

El generador reproduce escenarios con semilla y guarda un manifiesto sintético junto al archivo:

```sh
uv run python -m ivostock.generador.feeds --salida data/feeds/demo.csv --skus 1000 --semilla 7
uv run python -m ivostock.generador.feeds --base data/feeds/demo.csv --salida data/feeds/truncado.csv --truncar 0.3 --semilla 7
```

También permite `--ceros`, `--corruptas` y `--deriva`, como fracciones entre cero y uno. La salida conserva el encabezado fijo `SKU;stock`; los archivos locales son entradas de preparación y generación, y los proveedores se consultan siempre por HTTP.

## Recorrido de demostración

Dos terminales con el mismo `COMPOSE_PROJECT_NAME`: una de usuario y otra de backend. La sesión de usuario se abre con `docker compose run --rm user`; los comandos siguientes se escriben en `usuario>`:

```text
login                                            # Admin / Admin
store-add T1                                     # importa el catálogo en segundo plano
status stores
provider-add Celesa http://provider:8081/celesa.csv
suggest 1 T1 --limit 10 --positive-only
approve 1 T1 --count 3600 --positive-only
status links --store T1 --summary
status links --store T1 --limit 2
```

En la terminal de backend:

```sh
docker compose run --rm cli ivostock monitor --store T1 --watch --interval 15
docker compose kill -s SIGKILL catalog && docker compose start catalog
docker compose kill -s SIGKILL postgres && docker compose up -d --wait postgres
docker compose run --rm cli ivostock fault T1 429 --item ITEM000001 --remaining 1
docker compose run --rm cli ivostock fault T1 503 --item ITEM000002 --remaining 2
docker compose run --rm cli ivostock schedule-now 1
docker compose logs --no-color --timestamps publish | grep -E '"link": (1|2),'
```

`monitor` muestra llamadas de los últimos sesenta segundos según el cliente y según el simulador, progreso del catálogo, contadores de vínculos (`awaiting_ingest`, `pending`, `failed`, `synchronized`, `changed_from_initial`) e intentos por estado. Importar 127.564 publicaciones lleva unos 22 minutos y publicar 3.600 cantidades, alrededor de una hora: la cuota es la real. El alta del proveedor es una validación; la primera ingesta vence 300 minutos después y `schedule-now` la adelanta por el circuito normal.

## Recorrido manual paso a paso

Reemplazar `ARCHIVO.csv` por el nombre del inventario preparado. Los IDs numéricos se obtienen de la salida, sin asumir que empiezan en uno. Para una demostración determinista, detener primero los workers; los mismos servicios se ejecutan con los comandos de un paso.

```sh
docker compose stop ingest compare publish catalog
docker compose run --rm cli ivostock provider-add Celesa http://provider:8081/ARCHIVO.csv?no-changes=true
docker compose run --rm cli ivostock ingest ID_PROVEEDOR
docker compose run --rm cli ivostock seed T1 data/feeds/ARCHIVO.csv --count 1000
docker compose run --rm cli ivostock store-add T1 --wait
docker compose run --rm cli ivostock suggest ID_PROVEEDOR T1
docker compose run --rm cli ivostock approve ID_PROVEEDOR T1 --all
docker compose run --rm cli ivostock compare
docker compose run --rm cli ivostock status tasks
docker compose start ingest compare publish catalog
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

La ingesta automática ocurre cada 300 minutos, empezando 300 minutos después del alta, y no se superpone por proveedor. Los comandos manuales no cambian el próximo vencimiento; `schedule-now` lo adelanta. Las lecturas y escrituras comparten sesenta llamadas/minuto por tienda; reiniciar conserva el consumo.

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
