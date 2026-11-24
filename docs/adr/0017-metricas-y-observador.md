# ADR-0017: Estado de métricas interno y observador de sólo lectura

Estado: aceptado. Fecha: 17/11/2026.

## Contexto y alternativas

RNF-07 requiere medir disponibilidad durante 24 horas; RNF-02 exige p95 de publicación menor
que 30 minutos y p99 menor que 60 minutos en cada tienda. Son mediciones distintas: un proceso
puede estar activo mientras acumula trabajo. El equipo decidió observar el funcionamiento
normal, sin que el observador cambie feeds, dispare ingestas ni publique stock. La aplicación
ya dispone de `services.monitor`, estados durables, heartbeats y sesiones de operador.

Se compararon estas alternativas:

- **UptimeRobot u otro servicio alojado.** Resuelve consultas HTTP y presentación de uptime,
  pero no conoce los heartbeats ni los tiempos completos de publicación de Ivo Stock. Sigue
  haciendo falta instrumentar el sistema. El plan gratuito de UptimeRobot consulta cada cinco
  minutos, frente al minuto del protocolo; el plan Solo ofrece 60 segundos. También requiere
  conectividad desde el proveedor al entorno local y conservar una configuración externa para
  reproducir la corrección. Fuente consultada: [planes de UptimeRobot](https://uptimerobot.com/pricing/).
- **Sólo los health checks de Compose.** Ya existen y se reutilizan sus señales, pero su estado
  actual no conserva la serie por minuto ni los percentiles de efecto externo por tienda.
- **Prometheus y Grafana.** Adecuados para una operación más amplia, pero agregan servicios,
  almacenamiento y configuración para métricas cuyo origen ya está en PostgreSQL.
- **Servicio interno pequeño y observador propio.** Comparte las consultas, autenticación y
  estado existentes, permite arrancar localmente y separa la retención del acto de observar.
  El costo es mantener las consultas y una instrumentación mínima de los tiempos que faltan.

## Decisión

`ivostock.metrics_service` arranca con Compose y persiste como máximo una muestra por minuto
UTC en PostgreSQL. Conserva siete días. La API principal y este servicio exponen el mismo router
`api_metrics`: el tablero y servicio comparten las consultas operativas de la CLI existente.
Se reutilizan los health HTTP de API, simulador y proveedor y los heartbeats de los cuatro
workers. Se mantiene su tolerancia existente de 660 segundos: permite la ingesta de hasta diez
minutos sin confundir trabajo activo con una caída. No equivale a detectar una caída de worker
en sesenta segundos. API y motor se contabilizan por separado. El motor requiere los cuatro
heartbeats vigentes, incluso si no hay tareas.

Cada revisión publicable registra origen y efecto externo. El origen es la aceptación de la
corrida, o la creación del vínculo si ésta es posterior; para un corte, su intención registrada.
El simulador conserva y devuelve el primer `effect_at` de `X-Ivo-Work` (vínculo:revisión), de modo
que perder un acuse y repetir un envío no cambia el primer efecto ni multiplica las muestras.
Esto es instrumentación del simulador del TP, no una garantía sobre un marketplace real.
Una intención nueva de corte recibe una revisión propia incluso si el deseado ya era cero.

`ivostock.observer` es otro microservicio, desplegable por separado, que sólo hace GET al estado
interno y a los health HTTP. No tiene credenciales de PostgreSQL, volúmenes, temporizador de
escritura ni histórico propio. Cada consulta devuelve métricas JSON: no genera alertas, acciones,
notificaciones ni etiquetas de cumplimiento. El tablero también muestra valores numéricos.
La consulta requiere un token de operador validado por el servicio de métricas; no se crean
otra base de usuarios. El único login está en la API principal; métricas sólo valida el token
y expone `GET /auth/me`. Si la API cae, el token vigente permite seguir consultando; renovar
una sesión vencida espera su recuperación. El muestreo interno no depende de esa sesión.

Monitoreo es una herramienta de administración técnica. Para el TP sigue visible para todas
las cuentas precreadas porque comparten el único perfil de permisos existente. Esta excepción
documentada permite demostrar operación sin implementar RBAC. Los recorridos de negocio
conservan ocultos los detalles de infraestructura y los puntajes/versiones de ML; la vista
Monitoreo y `/metrics/*` son la superficie explícita de diagnóstico técnico. Separar usuarios
y administradores requiere aplicar autorización también en los endpoints, además de la vista.

Se reutiliza el componente declarado en el PR #18: `GET /health/live` de ML comprueba proceso y
esquema, y `GET /health` comprueba que puede servir inferencia. El entrenador conserva su
heartbeat de treinta segundos, compartido por su health CLI y HTTP. No se confunde calentamiento
(proceso activo e inferencia no lista) con ausencia del proceso. La disponibilidad del motor
de cuatro workers se calcula aparte: operar con reglas de respaldo no acredita disponibilidad
del modelo. El reporte de `ml.repository.report`, compartido con `ml-report`, aporta versión,
conteos por proveedor, mínimo de historial y aprendizaje pendiente; se persiste en la muestra
por minuto. El muestreo no entrena ni llama a `/classify` con datos nuevos.

## Consecuencias

El sistema registra su serie; el observador la consulta y contrasta la accesibilidad actual.
Una respuesta del observador no demuestra que éste estuviera funcionando en cada minuto anterior.
La disponibilidad histórica procede de las muestras internas, no de un historial externo
independiente. Se explicita este cambio de protocolo en PRD y SRD.

Las muestras faltantes cuentan en el denominador y no se rellenan con éxitos. Una caída de
PostgreSQL impide persistir muestras; una caída de métricas deja huecos. Sus health de proceso
y la edad del último estado permiten distinguir respuesta de vigencia. El despliegue local del
observador comparte máquina y red con el sistema; desplegarlo en otra máquina requiere acceso
a los endpoints, sin publicar PostgreSQL. Las métricas operativas y OpenAPI requieren sesión.

El ADR se numera 0017 y la migración de métricas 0008 para conservar los identificadores 0016 y
0007 de ML del PR #18. En el host, ML conserva 8002 y métricas usa 8004; dentro de cada contenedor
ambos procesos pueden usar 8002. Los volúmenes de la prueba anterior a esta integración se
conservan aparte: no se reinterpretan como una base que ya tenga la migración de ML.

Los percentiles se calculan sobre mediciones individuales, nunca promediando percentiles por
minuto. Se informan también pendientes, reemplazos y duraciones desconocidas; no se declara
cumplido RNF-02 si aún faltan efectos por confirmar. Una tienda sin muestras tiene percentiles
nulos. No se incorporan alertas ni pruebas sintéticas dentro del observador.

La migración `0009` sustituye el índice `(store_id, recorded_at)` de la migración `0008` por
índices de expresión sobre `COALESCE(origin_at, recorded_at)` para la ventana global y
`COALESCE(confirmed_at, superseded_at)` para la retención. Corresponden a los filtros reales:
la consulta selecciona el período antes de agrupar por tienda. PostgreSQL sigue decidiendo
si conviene usarlos según el tamaño de la tabla; no se fuerza un plan ni se atribuye una mejora
de rendimiento sin medirla.

## Comprobación

`tests/test_metrics.py` verifica muestreo único, retención, faltantes, independencia API/motor,
tiempos por tienda, conservación del primer efecto al perder un acuse, cortes y consultas sin
escritura. `tests/test_observer.py` verifica GET sin persistencia, autenticación y tratamiento
de errores sin exponer secretos. La campaña real de 24 horas queda registrada aparte y no se
da por realizada por aprobar estas pruebas.
