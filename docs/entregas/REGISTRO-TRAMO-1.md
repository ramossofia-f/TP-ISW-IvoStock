# Registro de verificación: tramo 28/10–03/11 (cuentas, API, interfaz y segunda tienda)

Este registro separa lo que se ejecutó de lo que sigue pendiente. Lo pendiente no se declara probado.

## Entorno de lo ejecutado (11/11/2026)

Linux x86-64 sin Docker, Python 3.12.3 con las dependencias de `uv.lock`, PostgreSQL 16 local y un servidor S3 simulado (moto 5.2.5) en lugar de MinIO. El simulador de marketplace y el proveedor de ensayo corrieron como procesos locales, con feeds sintéticos de 50 SKU. El feed real de Celesa no se usó. La versión de PostgreSQL y el almacén S3 difieren de los de Compose (PostgreSQL 15 y MinIO).

## Comprobado

| Verificación | Resultado |
|---|---|
| `uv run ruff check .` | Sin observaciones |
| `uv run pytest -q -m "not integration"` | 76 aprobadas |
| `uv run pytest -q` con `RUN_INTEGRATION=1`, contra PostgreSQL y S3 locales | 217 aprobadas en 101 s (incluye las 76 anteriores) |
| `scripts/verificar_documentacion.py` y `scripts/verificar_secretos.py` | Correctos |
| Recorrido de integración E1 (`tests/test_second_store.py::test_one_provider_run_updates_both_stores`) | Con sesión de operador: incorpora T1, da de alta el proveedor, aprueba, incorpora T2, aprueba, hace una sola ingesta y el cambio queda en ambas tiendas con solo las escrituras necesarias |
| Cinco operadores precreados con `configurar.py` e `inicializar.py` sobre una base migrada | Los cinco inician sesión en `POST /auth/login` y en la sesión `usuario>`; con contraseña errónea, 401 genérico |
| API real con `uvicorn` | `/health`, `/` y `/static/*` sin sesión; `/providers` sin token, 401; `/docs` y `/redoc`, 404; `/openapi.json`, 401 sin sesión y 200 con ella; sexto intento fallido de un usuario, 429 con `Retry-After` |
| `uv build --wheel` | El paquete incluye `ivostock/static/` |
| JavaScript de la interfaz | Sintaxis válida (`node --check`); sus llamadas coinciden con el OpenAPI (`tests/test_interface.py`) |

## No ejecutado

| Pendiente | Motivo |
|---|---|
| E2: recorrido manual en Docker con el feed real y la importación de T2 (~22 min) | No hubo Docker ni el feed real. Completar la tabla siguiente al hacerlo |
| Construcción de las imágenes y la prueba en contenedores (`docker compose --profile test run --build --rm tests`) | Sin Docker |
| Workflow de CI en GitHub | Sólo se ejecutaron localmente sus pasos de `checks`; el remoto no corrió |
| Interfaz en un navegador real | Sólo se verificó estáticamente, sin automatizar el comportamiento visual |
| Ensayos de capacidad, consultas y disponibilidad del MVP | Corresponden a otro tramo |

## Resultados del recorrido E2 (completar)

| Paso | Fecha y commit | Resultado observado |
|---|---|---|
| `make up` y `make provision` | pendiente | pendiente |
| Login en la interfaz con un operador de `data/operadores.txt` | pendiente | pendiente |
| Incorporar T1, alta de proveedor y vinculación | pendiente | pendiente |
| Incorporar T2 y duración de su importación con el feed real | pendiente | pendiente |
| Aprobación en T2 sin descargar al proveedor | pendiente | pendiente |
| Una ingesta y el cambio visible en T1 y T2 | pendiente | pendiente |
| Pestaña Corridas durante la ingesta | pendiente | pendiente |
