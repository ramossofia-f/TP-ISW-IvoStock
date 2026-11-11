# Decisiones de arquitectura

Los ADRs explican contexto, alternativas, decisión, consecuencias y comprobación. El [PRD](../prd/PRD.md) define el alcance y el [SRD](../srd/SRD.md), los contratos y la implementación.

| ADR | Decisión |
|---|---|
| [0001](0001-python-fastapi.md) | Python y FastAPI |
| [0002](0002-postgresql-compartido.md) | PostgreSQL compartido y procesos separados |
| [0003](0003-snapshots-s3.md) | Snapshots inmutables en S3 |
| [0004](0004-cola-postgresql.md) | Cola durable y reemplazo por vínculo |
| [0005](0005-cuota-postgresql.md) | Cuota durable por tienda |
| [0006](0006-marketplace-http.md) | Marketplace simulado por HTTP |
| [0007](0007-inventarios-deltas.md) | Inventarios completos, deltas y escenarios reproducibles |
| [0008](0008-contenedores-ci.md) | Contenedores y CI |
| [0009](0009-catalogo-en-segundo-plano.md) | Importación de catálogo en segundo plano con punto de control |
| [0010](0010-cuentas-y-sesiones.md) | Cuentas de operador precreadas y sesiones en PostgreSQL |
| [0011](0011-api-de-configuracion.md) | API de configuración sobre `services` con errores tipados |
| [0012](0012-tiendas-aprovisionadas-y-rotacion.md) | Tiendas aprovisionadas fuera de la aplicación y rotación de la importación |
| [0013](0013-interfaz-estatica.md) | Interfaz de configuración estática servida por la API |
| [0014](0014-contrato-privado-y-limite-de-intentos.md) | Contrato OpenAPI privado y límite de intentos de login |

Las mediciones se registran en la [evidencia E2](../entregas/ENTREGA-2.md). ML está pendiente de definición para el MVP.
