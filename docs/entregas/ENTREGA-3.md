# Evidencia de la Entrega 3

Entrega: 24/11/2026. El alcance está en el [PRD](../prd/PRD.md), el diseño en el [SRD](../srd/SRD.md), las decisiones en los [ADRs](../adr/README.md) y los comandos en el [README](../../README.md). Esta página reúne lo comprobado para el MVP y remite a cada reporte; no repite sus tablas completas.

## Resumen

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Suite automatizada al cierre | 376 pruebas: 193 unitarias y 183 de integración contra PostgreSQL y S3 | Jobs `checks` e `integration` sobre `develop` (`b82c183`) |
| Pruebas unitarias (`pytest -m "not integration"`) en el CI remoto | 193 aprobadas | Job `checks` sobre `develop` (`b82c183`) |
| Pruebas unitarias e integración dentro de Docker en el CI remoto | 375 aprobadas, 1 omitida | Job `integration` sobre `develop` (`b82c183`) |
| Validación de despliegue en el CI remoto | Aprobada | Job `despliegue` sobre `develop` |
| Decisiones de arquitectura | 18 ADRs; el ADR-0016 reemplaza al ADR-0015 | [Índice de ADRs](../adr/README.md) |
| RNF-02: publicación en dos tiendas con 1.000 vínculos cada una | Cumple con Celesa: p95 de 15,1 y 16,0 min, p99 de 16,1 y 16,2 min (objetivo p95 < 30, p99 < 60) | [Ensayo con Celesa](ENSAYO-DOS-TIENDAS-CELESA.md), PR #21 |
| RNF-15: 2.000 vínculos totales, 1.000 por tienda | Demostrado con Celesa (255.129 SKU) y con el feed sintético | [Celesa](ENSAYO-DOS-TIENDAS-CELESA.md), [sintético](ENSAYO-DOS-TIENDAS-SINTETICO.md) |
| RNF-09: cinco operadores a una consulta/s durante 30 min, motor activo | Cumple con Celesa: 9.000 consultas, p95 de 18 ms, p99 de 20 ms, cero errores, 2.835 publicaciones concurrentes | [Ensayo de consultas](ENSAYO-CONSULTAS-CELESA.md), PR #25 |
| RNF-07: disponibilidad de 24 horas | Cumple: 1.440 de 1.440 muestras, 100 % para API y motor (umbral 99 %) | [Resultado de la campaña](RNF07-RESULTADO-COMPLETO-20261119.md), PR #31 |
| ML: activación tras diez aceptados del proveedor | Grabada para el video sobre `219b928`: corrida 10 aceptada por la guarda, nueva versión con 10 observaciones y corrida 11 decidida con `decision_source: ml` | [Demostración de ML](ENTREGA-3-ML-PENDIENTES.md), [verificación](ML-NORMALIDAD-VERIFICACION.md) |
| Readiness cloud | Desplegado el 22/11 en AWS `us-east-2`: 11 servicios sanos, una corrida aceptada y snapshot en S3; entorno destruido después | [Guía de despliegue](../despliegue/AWS.md), PR #28 |

## Qué incorpora el MVP

| Resultado | Requisito | PR |
|---|---|---|
| API de configuración, cuentas precreadas, login con límite de intentos e interfaz de configuración | RF-01, RF-25, RNF-11 | #12, #14 |
| Segunda tienda reutilizando el inventario del proveedor | RNF-15 | #13 |
| Tablero de corridas y búsqueda de sugerencias por SKU | RF-25 | #14 |
| Modificación de nombre y URL del proveedor | RF-04 | #22 |
| Fallas definitivas en la interfaz | RF-25 | #26 |
| Detector global de normalidad con guarda obligatoria, inferencia y entrenamiento separados | RF-27 | #18, #27 |
| Métricas persistidas y observador de disponibilidad | RNF-07 | #19 |
| Despliegue efímero en AWS y job de CI | ADR-0018 | #28 |

## Recortes de alcance

La devolución de la Entrega 1 observó alcance excesivo. Se aplicaron estos recortes, ya reflejados en el PRD:

| Antes | Después | Motivo |
|---|---|---|
| 100.000 vínculos totales en dos tiendas | 2.000 vínculos, 1.000 por tienda (RNF-02, RNF-15) | Escala demostrable con la cuota real de 60 llamadas por minuto y tienda |
| Capacidad de consulta para 1.000 usuarios a una consulta/s, bajada luego a 50 | Cinco operadores autenticados a una consulta/s (RNF-09) | Proporcional a una herramienta interna de catálogo y publicaciones |
| Cuota diaria de operaciones por usuario y cuota de 60 solicitudes por minuto a la API por usuario | Pasaron a deseables y quedaron fuera del MVP | Primeros en el orden de recorte |

Durante el MVP no hizo falta aplicar el orden de recorte del supuesto S-08: RF-04 (*Should*) se completó y RNF-09 y RNF-15 se midieron a la escala declarada.

## Límites declarados

- La campaña de RNF-07 usó carga sintética (semilla 7, 2.000 SKU), porque el archivo de Celesa no estaba en el equipo del laboratorio. Mide disponibilidad interna según el ADR-0017; no es una sonda funcional externa.
- Los ensayos de RNF-02 y RNF-09 corrieron en un equipo local con 10 CPU y 7,7 GiB compartidos, sin límites por contenedor.
- Monitoreo técnico es visible para todas las cuentas precreadas. Es una simplificación del TP: no se implementó un rol administrador (ADR-0017).
- Las corridas del video que preparan la activación del ML se dispararon a mano con `ivostock ingest`; no son un histórico de producción.

## Video

https://youtu.be/EWXwMQDCltY. Muestra el recorrido de usuario y, por separado, el de administración, incluida la activación del ML en la corrida 11.
