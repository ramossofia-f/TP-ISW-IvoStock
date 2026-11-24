# ADR-0008: Contenedores, Compose y CI

Estado: aceptado. Fecha: 25/10/2026. Alternativas desarrolladas el 18/11/2026.

## Contexto y alternativas

El equipo y la cátedra deben ejecutar el mismo circuito localmente, en macOS, Windows o Linux, con un comando después de instalar Docker (RNF-13). Para el arranque se compararon tres alternativas:

- **Instalación manual de servicios.** No agrega herramientas. Pero cada máquina termina con versiones distintas de PostgreSQL, MinIO y Python, y los pasos manuales son difíciles de reproducir para quien corrige.
- **Docker Compose.** Un archivo versionado describe procesos, volúmenes, health checks y orden de arranque, y el mismo circuito corre en cualquier máquina con Docker. A cambio, requiere Docker y recursos para todos los servicios, el primer build necesita red, y no representa un despliegue productivo en varios nodos.
- **Orquestador de clúster, como Kubernetes.** Da alta disponibilidad y escalado. Pero su complejidad operativa es desproporcionada para un MVP local y exige además un clúster local para probar.

Para la verificación continua se compararon comprobaciones manuales, un servidor de CI propio y un workflow versionado junto al código:

- **Comprobaciones manuales.** No requieren configuración, pero dependen de que alguien las corra y no dejan registro.
- **Servidor de CI propio.** Da control total, pero hay que operarlo y mantenerlo.
- **Workflow de GitHub Actions versionado.** Se repite igual en cada push, no requiere operar nada y deja el resultado en el PR. A cambio, depende del servicio externo: si no corre, por ejemplo por un bloqueo de facturación, no hay verificación remota.

## Decisión

Usar imágenes de aplicación con dependencias bloqueadas, Compose para los procesos, PostgreSQL con volumen y MinIO con volumen. La configuración se genera por entorno con secretos aleatorios. Los puertos locales se enlazan a loopback. Hay migración y creación de bucket antes del arranque, health checks y reinicio de procesos.

MinIO se construye desde la etiqueta oficial `RELEASE.2025-10-15T17-29-55Z`, siguiendo su [distribución desde código fuente](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z). El primer build requiere descargar el toolchain y las dependencias; el builder no forma parte de la imagen final.

## Consecuencias

El primer arranque requiere red; los datos sobreviven al reemplazo de contenedores. Los volúmenes deben respaldarse y no se eliminan en el apagado habitual. La preparación local no acredita despliegue cloud ni disponibilidad de producción.

## Comprobación

CI construye imágenes y ejecuta pruebas, integración y comprobaciones documentales. El arranque local verifica servicios saludables y el circuito por CLI. Las mediciones se registran con versiones, datos y recursos.

GitHub Actions ejecuta análisis estático y unitarias por separado de la integración con servicios reales. Su presencia no acredita una ejecución remota: el equipo comprueba el resultado antes de entregar.
