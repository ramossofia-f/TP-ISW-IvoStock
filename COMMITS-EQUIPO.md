# Reparto y coautoría de los commits de entrega

Los cambios se organizan en nueve commits desde este repositorio, con Francisco Ortega como autor Git y las coautorías que corresponden a cada área. El responsable del bloque identifica el reparto de trabajo; no cambia la identidad del autor configurado en Git.

Base del trabajo: `691d60eb6e668fa07c996b48f8b8338fb3ed0a48`. El reparto cubre 85 archivos y eliminaciones, con tres bloques por responsable.

## Criterio de coautoría

P0 y P5 son compartidos. P1 corresponde a Francisco con apoyo de Sofía; P4, a Francisco con apoyo de María. P2 corresponde a María con apoyo de Sofía. P3 corresponde a Sofía con apoyo de Francisco. Francisco figura como autor; los aportes de sus compañeras se registran con trailers Co-authored-by y sus emails de GitHub.

| Orden | Bloque | Responsable | Coautoras |
|---|---|---|---|
| 1 | `chore(p0): preparar paquete y entorno reproducible` | Francisco Ortega | María Saráchaga, Sofía Ramos |
| 2 | `feat(p2): persistir inventarios y generar escenarios reproducibles` | María Saráchaga | María Saráchaga, Sofía Ramos |
| 3 | `feat(p2): normalizar inventarios y evaluar cuarentena` | María Saráchaga | María Saráchaga, Sofía Ramos |
| 4 | `feat(p3): comparar vínculos y publicar trabajo durable` | Sofía Ramos | Sofía Ramos |
| 5 | `feat(p1,p4): implementar marketplace y operación de vínculos` | Francisco Ortega | María Saráchaga, Sofía Ramos |
| 6 | `chore(p5): verificar fallas y exponer diagnóstico seguro` | Sofía Ramos | María Saráchaga, Sofía Ramos |
| 7 | `docs(p2): precisar contrato de datos y propuesta del producto` | María Saráchaga | María Saráchaga, Sofía Ramos |
| 8 | `docs(p5): describir diseño y registrar evidencia de aceptación` | Sofía Ramos | María Saráchaga, Sofía Ramos |
| 9 | `docs(p5): documentar operación y preparar entrega del equipo` | Francisco Ortega | María Saráchaga, Sofía Ramos |

## Archivos por commit

### 1. `chore(p0): preparar paquete y entorno reproducible`

Empaquetado y dependencias bloqueadas; configuración por entorno, PostgreSQL/MinIO, volúmenes y arranque reproducible. Retirar el import de paquete desde src y documentar las decisiones de ejecución.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `.dockerignore` |
| Actualizar/crear | `.env.example` |
| Actualizar/crear | `.gitignore` |
| Actualizar/crear | `Dockerfile` |
| Actualizar/crear | `Makefile` |
| Actualizar/crear | `docker-compose.yml` |
| Actualizar/crear | `docker/minio.Dockerfile` |
| Actualizar/crear | `pyproject.toml` |
| Actualizar/crear | `uv.lock` |
| Actualizar/crear | `scripts/configurar.py` |
| Actualizar/crear | `scripts/inicializar.py` |
| Actualizar/crear | `src/ivostock/config.py` |
| Eliminar | `src/__init__.py` |
| Actualizar/crear | `docs/adr/0001-python-fastapi.md` |
| Actualizar/crear | `docs/adr/0008-contenedores-ci.md` |
| Eliminar | `docs/adr/0004-lenguaje-y-framework.md` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 2. `feat(p2): persistir inventarios y generar escenarios reproducibles`

Persistencia SQL, migraciones y aislamiento de la base de pruebas; generador sintético con semilla, parámetros y hashes. Documentar almacenamiento y base compartida.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `src/ivostock/db.py` |
| Actualizar/crear | `src/ivostock/schema.sql` |
| Actualizar/crear | `alembic.ini` |
| Actualizar/crear | `migrations/env.py` |
| Actualizar/crear | `migrations/versions/0001_inventory.py` |
| Actualizar/crear | `migrations/versions/0002_run_correlation.py` |
| Actualizar/crear | `src/ivostock/generador/__init__.py` |
| Actualizar/crear | `src/ivostock/generador/feeds.py` |
| Actualizar/crear | `tests/generador/__init__.py` |
| Actualizar/crear | `tests/generador/test_feeds.py` |
| Actualizar/crear | `tests/conftest.py` |
| Actualizar/crear | `docs/adr/0002-postgresql-compartido.md` |
| Actualizar/crear | `docs/adr/0003-snapshots-s3.md` |
| Eliminar | `docs/adr/0005-almacenamiento.md` |
| Eliminar | `docs/adr/0007-intercambio-api-motor.md` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 3. `feat(p2): normalizar inventarios y evaluar cuarentena`

Contrato fijo SKU;stock, SKU como texto, descartes de duplicados, coeficiente D/Z, snapshots y aceptación/cuarentena transaccional. Conservar eventos durables y reutilizar inventarios idénticos; probar las fallas de P2.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `src/ivostock/feed.py` |
| Actualizar/crear | `src/ivostock/ingesta/__init__.py` |
| Actualizar/crear | `src/ivostock/ingesta/coeficiente.py` |
| Actualizar/crear | `src/ivostock/ingesta/fuente.py` |
| Actualizar/crear | `src/ivostock/ingesta/normalizacion.py` |
| Actualizar/crear | `src/ivostock/ingesta/servicio.py` |
| Actualizar/crear | `src/ivostock/storage.py` |
| Actualizar/crear | `scripts/analizar_feed.py` |
| Actualizar/crear | `tests/test_feed.py` |
| Actualizar/crear | `tests/ingesta/__init__.py` |
| Actualizar/crear | `tests/ingesta/test_normalizacion.py` |
| Actualizar/crear | `tests/ingesta/test_coeficiente.py` |
| Actualizar/crear | `tests/ingesta/test_servicio.py` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 4. `feat(p3): comparar vínculos y publicar trabajo durable`

Comparación contra confirmado, FIFO con reemplazo, cuota por tienda, leases, reintentos, dead letters y cortes persistidos. Incorporar pruebas de recuperación y confirmaciones atrasadas y retirar el comparador genérico.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `src/ivostock/comparison.py` |
| Actualizar/crear | `src/ivostock/publisher.py` |
| Actualizar/crear | `src/ivostock/quota.py` |
| Actualizar/crear | `src/ivostock/worker.py` |
| Actualizar/crear | `src/ivostock/failpoints.py` |
| Actualizar/crear | `tests/test_pipeline.py` |
| Eliminar | `src/ivostock/comparador/__init__.py` |
| Eliminar | `src/ivostock/comparador/worker.py` |
| Eliminar | `tests/test_comparador.py` |
| Actualizar/crear | `docs/adr/0004-cola-postgresql.md` |
| Actualizar/crear | `docs/adr/0005-cuota-postgresql.md` |
| Eliminar | `docs/adr/0002-propagacion-por-deltas.md` |
| Eliminar | `docs/adr/0006-cola-de-tareas-en-postgresql.md` |

Trailers del mensaje:

```text
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 5. `feat(p1,p4): implementar marketplace y operación de vínculos`

Contrato HTTP del simulador y catálogo estático; incorporación de tiendas, aprobación y operación de vínculos, CLI y health de la API. Revisar credenciales, paginación y corte seguro con sus responsables.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `src/ivostock/cli.py` |
| Actualizar/crear | `src/ivostock/main.py` |
| Actualizar/crear | `src/ivostock/marketplace.py` |
| Actualizar/crear | `src/ivostock/services.py` |
| Actualizar/crear | `src/ivostock/simulator.py` |
| Actualizar/crear | `docs/adr/0006-marketplace-http.md` |
| Eliminar | `docs/adr/0001-marketplace-simulado-detras-de-interfaz.md` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 6. `chore(p5): verificar fallas y exponer diagnóstico seguro`

CI, logs estructurados sin secretos, health checks, observador de ensayos y verificadores. Comprobar integración y cierres abruptos con servicios reales, sin conservar el test trivial.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `.github/workflows/ci.yml` |
| Actualizar/crear | `src/ivostock/health.py` |
| Actualizar/crear | `src/ivostock/logs.py` |
| Actualizar/crear | `tests/test_logs.py` |
| Eliminar | `tests/test_dummy.py` |
| Actualizar/crear | `scripts/pruebas_locales.py` |
| Actualizar/crear | `scripts/verificar_documentacion.py` |
| Actualizar/crear | `scripts/verificar_secretos.py` |
| Actualizar/crear | `scripts/evaluar_poc.py` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 7. `docs(p2): precisar contrato de datos y propuesta del producto`

Requisitos y presentación del producto acordado; contrato de fuentes y límites demostrables. ML queda pendiente; la validación determinista sigue siendo una regla del motor.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `docs/prd/PRD.md` |
| Actualizar/crear | `docs/prd/validacion.md` |
| Actualizar/crear | `docs/adr/0007-inventarios-deltas.md` |
| Eliminar | `docs/adr/0003-componente-ml-deteccion-anomalias.md` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 8. `docs(p5): describir diseño y registrar evidencia de aceptación`

Diseño técnico e índice de decisiones, junto con evidencia real de aceptación. Distinguir las mediciones ejecutadas del trabajo pendiente para el MVP y para la entrega remota.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `docs/srd/SRD.md` |
| Actualizar/crear | `docs/entregas/ENTREGA-2.md` |
| Actualizar/crear | `docs/adr/README.md` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

### 9. `docs(p5): documentar operación y preparar entrega del equipo`

Guías de ejecución, reglas del repositorio, hitos y reparto de entrega. El exportador prepara un ZIP sin secretos ni Git y sólo copia a cada clon sus archivos asignados.

| Acción | Archivo |
|---|---|
| Actualizar/crear | `README.md` |
| Actualizar/crear | `CLAUDE.md` |
| Actualizar/crear | `COMMITS-EQUIPO.md` |
| Actualizar/crear | `docs/roadmap/ROADMAP.md` |
| Actualizar/crear | `scripts/reparto_commits.py` |

Trailers del mensaje:

```text
Co-authored-by: María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>
Co-authored-by: Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>
```

## Comprobación y publicación

Verificar el conjunto con los comandos del README y revisar los autores y trailers con `git log --format=full` desde la base indicada. El índice de archivos se comprueba con `python scripts/reparto_commits.py verificar`.

Los commits son locales. Quedan pendientes el push, la comprobación de CI remoto y el video de entrega. El PR #6 contiene aportes ya adaptados a este árbol; coordinar su cierre después de aceptar la integración para evitar duplicarla. No se modifica su rama ni se hace force-push.
