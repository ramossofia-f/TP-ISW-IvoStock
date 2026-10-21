# Ivo Stock
## TP integrador, Ingeniería de Software

**Grupo:** 

- Sofía Ramos (https://github.com/ramossofia-f)
- Maria Saráchaga (https://github.com/mariasarachaga)
- Francisco Ortega (https://github.com/fortega00)

**Estado:** Entrega 1 aprobada; revisión del PRD y del roadmap en curso según la devolución de la cátedra.

Ivo Stock sincroniza inventario entre N fuentes de stock y K tiendas de MercadoLibre. El objetivo es que sumar un proveedor o una tienda sea una operación de configuración y no el desarrollo de un script nuevo por cada par proveedor–tienda.

La demostración del MVP está acotada a **2 tiendas simuladas y 100.000 vínculos activos totales, 50.000 por tienda**. Se verificará el paso de una a dos tiendas sobre el mismo proveedor sin modificar código ni duplicar la ingesta. El perfil de deltas por corrida sigue pendiente de acordar; la capacidad para más tiendas requiere nuevas mediciones.

La API detrás de la interfaz tiene como objetivo **1.000 usuarios activos a una consulta por segundo cada uno, con p95 menor a 2 segundos**, y una cuota de **60 solicitudes por minuto por usuario**. Ante un 429, la interfaz conserva la pantalla e informa cuánto esperar según `Retry-After`. La prueba se ejecutará con el motor activo y con bases de datos y CPU separados; el cumplimiento todavía debe demostrarse (RNF-20 a RNF-22).

El diseño prevé una interfaz web con su API y un motor de sincronización independientes, con bases de datos y CPU propios e intercambio asíncrono y durable. El objetivo es conservar todo el trabajo pendiente ante cierres abruptos, alcanzar al menos 99 % de disponibilidad por conjunto durante una prueba de 24 horas y reanudar el motor en hasta 10 minutos. Estos requisitos están pendientes de implementación; el protocolo verificable está en [PRD §4](docs/prd/PRD.md#4-requisitos-no-funcionales) y su construcción en el [roadmap](docs/roadmap/ROADMAP.md).

Las llamadas a MercadoLibre mantienen un máximo de **60 req/min por tienda**: **40 para sincronización habitual y 20 para operaciones masivas**, con préstamo del cupo que una clase deje ocioso. La política de admisión de trabajos masivos sigue en revisión.

### Instrucciones para acceder a cada componente del desarrollo

#### Entrega 1

- PRD: problema, usuarios, casos de uso, requisitos funcionales y no funcionales, criterios de éxito, fuentes de datos, viabilidad, riesgos, supuestos, limitaciones y componente de Machine Learning.
- Roadmap: hitos, orden de construcción y criterios de salida para el POC (Entrega 2) y el MVP (Entrega 3).
- ADRs: decisiones estructurales del proyecto, con alternativas consideradas y trade-offs.
- Validación de proyecto: registro histórico de la propuesta enviada a la cátedra; el alcance vigente está en el PRD.

Video: https://www.youtube.com/watch?v=zP0HYAmsSoY
