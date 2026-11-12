# Trabajo en Ivo Stock

El [PRD](docs/prd/PRD.md) define el producto; el [SRD](docs/srd/SRD.md), su diseño; los [ADRs](docs/adr/0001-python-fastapi.md), las decisiones. El [README](README.md) contiene comandos y el [roadmap](docs/roadmap/ROADMAP.md), estado y evidencias.

## Reglas de implementación

- Mantener separados los procesos de ingesta, comparación, publicación e importación de catálogo, con PostgreSQL compartido y snapshots S3.
- La aplicación nunca crea tiendas ni usa la credencial de control: las tiendas se aprovisionan con `scripts/provisionar_tiendas.py`, se incorporan con `services.incorporate_store` y sólo si figuran en `MARKETPLACE_STORES`.
- Los endpoints de configuración sólo llaman a `ivostock.services`; los errores de negocio son subclases de `ServiceError` con mensajes sin URLs, tokens ni texto de excepciones externas, y los listados no devuelven la URL del proveedor.
- Todo endpoint de la API, salvo `/health` y `/auth/login`, depende de `require_operator`; las cuentas se precrean desde `OPERATOR_ACCOUNTS` y las contraseñas nunca van a Git. La única excepción es la interfaz estática (`/` y `/static/*`, fuera de OpenAPI), que no debe servir datos. Swagger UI y ReDoc están apagados y `/openapi.json` exige sesión ([ADR-0014](docs/adr/0014-contrato-privado-y-limite-de-intentos.md)); el login se bloquea tras varios fallos del mismo usuario.
- La interfaz vive en `src/ivostock/static/`, sólo llama a endpoints documentados en OpenAPI e inserta los datos como texto: nunca `innerHTML`, manejadores ni estilos en línea ([ADR-0013](docs/adr/0013-interfaz-estatica.md)).
- La sesión `usuario>` autentica con esas cuentas y sólo expone comandos de usuario; los de ensayo y operación (`fault`, `schedule-now`, `monitor`) quedan en la CLI de backend.
- Los proveedores cumplen un único contrato HTTP; el parser y la guarda están en `ivostock.ingesta`, con preparación y acceso desde `ivostock.feed`.
- La intención de cero es durable y precede al stock del proveedor. El vínculo sólo se desactiva después de confirmarla.
- Una confirmación atrasada no elimina una revisión nueva. La cuota persiste y se comparte entre lecturas y escrituras.
- Reanudar fallas usa el último estado deseado; la evidencia anterior se conserva.
- Configuración sensible por entorno. Datos reales, derivados, evidencias crudas y secretos fuera de Git.
- Los endpoints de control del simulador son herramientas de ensayo, separados de su API de negocio.
- Agregar decisiones estructurales como ADRs breves con alternativas y consecuencias.
- Mantener alcance, comandos y resultados medidos coherentes. No declarar pruebas que no se ejecutaron.
- ML está pendiente de definición para el MVP.

## Comprobación

```sh
uv sync --frozen
uv run ruff check .
uv run pytest -q -m "not integration"
uv run python scripts/verificar_documentacion.py
uv run python scripts/verificar_secretos.py
```

Las pruebas de integración usan exclusivamente `ivostock_test` y el bucket `snapshots-test`, según el README. Las instrucciones explícitas del usuario tienen precedencia.
