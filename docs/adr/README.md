# ADRs

Cada ADR registra una decisión estructural y compara las alternativas consideradas. El formato es el mismo en todos: contexto y problema, factores de decisión, opciones consideradas, decisión con sus consecuencias y su confirmación, y ventajas y desventajas de cada opción.

| ADR | Decisión |
|---|---|
| [0001](0001-marketplace-simulado-detras-de-interfaz.md) | Marketplace simulado detrás de una interfaz única |
| [0002](0002-propagacion-por-deltas.md) | Propagación por deltas contra el estado vigente |
| [0003](0003-componente-ml-deteccion-anomalias.md) | Componente de ML: detección de anomalías en corridas de feed |
| [0004](0004-lenguaje-y-framework.md) | Python con FastAPI para la API, los workers y el simulador |
| [0005](0005-almacenamiento.md) | PostgreSQL, almacenamiento de objetos y Redis |
| [0006](0006-cola-de-tareas-en-postgresql.md) | Cola de tareas durable en PostgreSQL |
| [0007](0007-intercambio-api-motor.md) | Intercambio entre la API y el motor por replicación lógica, en dos servidores |
| [0008](0008-arquitectura-servicios-con-cola.md) | Arquitectura de servicios separados, integrados por una cola de tareas |
| [0009](0009-docker-compose.md) | Docker Compose para el entorno local |
| [0010](0010-ci-cd.md) | Integración y despliegue continuos con GitHub Actions |
| [0011](0011-observabilidad.md) | Observabilidad por servicio y observador externo |
| [0012](0012-generadores-sinteticos.md) | Generadores sintéticos reproducibles con semilla |

Quedan pendientes el framework del frontend (M1) y la estrategia de cálculo de deltas, que se decide con las mediciones de RNF-02 en P2.

Los ADRs describen decisiones de diseño. No acreditan resultados de rendimiento ni de disponibilidad: esos se verifican con las pruebas del PRD §4.
