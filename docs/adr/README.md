# ADRs

Los ADR-0001 a ADR-0003 están aceptados. Los ADR-0004 a ADR-0018 son propuestas de diseño, pendientes de revisión e implementación; no acreditan resultados de rendimiento o disponibilidad.

Cada propuesta conserva la estructura MADR de los ADRs existentes: contexto, criterios, alternativas, decisión, consecuencias y verificación.

| Componente o decisión | ADR |
|---|---|
| Interfaz de marketplace y simulador | [0001](0001-marketplace-simulado-detras-de-interfaz.md) |
| Estrategia de propagación por deltas | [0002](0002-propagacion-por-deltas.md) |
| Pipeline de ML: entrenamiento, serving y monitoreo | [0003](0003-componente-ml-deteccion-anomalias.md) |
| Frontend web | [0004](0004-frontend-web.md) |
| API core | [0005](0005-api-core.md) |
| Worker de ingesta | [0006](0006-worker-ingesta.md) |
| Worker comparador | [0007](0007-worker-comparador.md) |
| Worker de publicación | [0008](0008-worker-publicacion.md) |
| Worker de catálogo | [0009](0009-worker-catalogo.md) |
| PostgreSQL | [0010](0010-postgresql.md) |
| Object storage S3 / MinIO | [0011](0011-object-storage-s3-minio.md) |
| Redis: planificación, cuotas e intercambio | [0012](0012-redis-cola-y-cuotas.md) |
| Orquestación local con Docker Compose | [0013](0013-docker-compose.md) |
| Pipeline de CI/CD | [0014](0014-pipeline-ci-cd.md) |
| Logs, métricas, health checks y observador externo | [0015](0015-observabilidad.md) |
| Generador de feeds | [0016](0016-generador-feeds.md) |
| Generador de catálogo | [0017](0017-generador-catalogo.md) |
| API y motor en servidores separados | [0018](0018-api-y-motor-en-servidores-separados.md) |

La cobertura toma los componentes de [CLAUDE.md](../../CLAUDE.md), el [PRD](../prd/PRD.md) y el [roadmap](../roadmap/ROADMAP.md). El [documento de validación](../prd/validacion.md) se usa como antecedente histórico; ante diferencias prevalece el PRD vigente. El ADR-0007 complementa la estrategia del ADR-0002 con la responsabilidad del worker comparador.

Los frameworks de frontend y backend, el proveedor de CI/hosting y la herramienta de observabilidad siguen pendientes. Sus menciones como candidatos no se convierten en decisiones aceptadas mediante estos ADRs.
