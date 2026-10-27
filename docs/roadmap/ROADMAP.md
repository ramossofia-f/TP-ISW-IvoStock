# Roadmap de Ivo Stock

El alcance está en el [PRD](../prd/PRD.md); el diseño en el [SRD](../srd/SRD.md). Esta página registra entregables y evidencia sin duplicar requisitos.

## Entrega 2 — 27/10/2026

| Paso | Entregable | Estado / evidencia |
|---|---|---|
| 1 | Alcance, contratos, SRD y nueve ADRs | Implementado; verificación de referencias automatizada |
| 2 | Paquete, configuración, Compose e imágenes | Comprobado: imágenes construidas y servicios saludables |
| 3 | Preparación y servicio HTTP de datos reales | Herramienta implementada; evidencia del feed real en el registro E2 |
| 4 | Migraciones, estado y snapshots | Implementado; integración con PostgreSQL y MinIO |
| 5 | Simulador HTTP con cuota y fallas | Implementado; pruebas por TCP |
| 6 | Ingesta, programación y cuarentena | Implementado; pruebas de contrato y programación |
| 7 | Comparación, eventos y cola por vínculo | Implementado; pruebas de reemplazo y recuperación |
| 8 | Publicador, cuota, reintentos y dead letters | Implementado; pruebas de cuota y fallas |
| 9 | CLI y corte a cero | Implementado; pruebas de corte y revisión manual |
| 9b | Sesión de usuario, catálogo en segundo plano, proveedor con variantes y monitor | Implementado; pruebas de reanudación del catálogo, aprobación previa a la ingesta, baja de proveedor, fuente inaccesible y credencial revocada |
| 10 | Cierres abruptos, caída de base y CI | 68 pruebas en Docker y ensayo real aprobados; workflow remoto por comprobar |
| 11 | Coherencia documental y guía ejecutable | Verificadores y recorrido del README |
| 12 | Video público de 5–12 minutos y commits de entrega | Commits locales organizados con coautorías del equipo; pendientes push, video y comprobación de CI remoto |

El [registro E2](../entregas/ENTREGA-2.md) contiene los resultados concretos. La existencia de un workflow no acredita que haya ejecutado en el servidor remoto.

## MVP — 24/11/2026

| Tramo | Resultado verificable | Tamaño | Referente | Apoyo |
|---|---|---|---|---|
| 28/10–03/11 | Cuentas precreadas, login e interfaz de configuración; incorporar segunda tienda desde la app reutilizando inventario | Grande | Francisco Ortega | María Saráchaga |
| 04/11–10/11 | Tablero y búsqueda; completar modificación de proveedor y comprobaciones de autorización | Mediano | María Saráchaga | Sofía Ramos |
| 11/11–17/11 | Definir componente ML, datos y evaluación; implementar entrenamiento, inferencia y monitoreo reproducibles | Grande | Sofía Ramos | Francisco Ortega |
| 18/11–24/11 | Medir dos tiendas (RNF-02, RNF-15), consultas (RNF-09) y disponibilidad (RNF-07); completar automatización, evidencia y defensa | Mediano | Los tres: Sofía Ramos dos tiendas, María Saráchaga consultas y Francisco Ortega disponibilidad | — |

El referente coordina el tramo, abre su pull request y responde por su criterio de salida; el apoyo revisa ese pull request. El trabajo se comparte: cuando varios integrantes resuelven algo juntos, el commit lleva a quien lo escribió como autor y a los demás como coautores. El tamaño es relativo al tramo de una semana de tres integrantes. Si un tramo se atrasa más de dos días se aplica el orden de recorte del supuesto S-08 del [PRD](../prd/PRD.md) antes de empezar el siguiente.

Los ensayos de publicación, consulta y disponibilidad tienen ventanas separadas, recursos y perfiles declarados. La cantidad y frecuencia de cambios se registran, sin límite de admisión por deltas. El componente de ML requiere una decisión específica antes de implementarlo.

## Preparación de la presentación E2

Guion sugerido de ocho minutos: problema y contrato (1), arquitectura y datos reales (1), ingesta y vinculación (2), cambio y confirmación (1), cuarentena/dead letter/reanudación (1), corte y recuperación (1), pruebas y límites demostrados (1). Usar los comandos y el reporte reales, ocultando secretos y sin mostrar inventario privado completo. Identificar el commit probado en `main` al presentar el enlace del video y conservar las contribuciones reales del equipo.
