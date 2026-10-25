# ADR-0008: Contenedores, Compose y CI

Estado: aceptado. Fecha: 25/10/2026.

## Contexto y alternativas

El equipo y la cátedra deben ejecutar el mismo circuito localmente. Se comparan instalación manual de servicios, Compose y un orquestador de clúster.

## Decisión

Usar imágenes de aplicación con dependencias bloqueadas, Compose para los procesos, PostgreSQL con volumen y MinIO con volumen. La configuración se genera por entorno con secretos aleatorios. Los puertos locales se enlazan a loopback. Hay migración y creación de bucket antes del arranque, health checks y reinicio de procesos.

MinIO se construye desde la etiqueta oficial `RELEASE.2025-10-15T17-29-55Z`, siguiendo su [distribución desde código fuente](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z). El primer build requiere descargar el toolchain y las dependencias; el builder no forma parte de la imagen final.

## Consecuencias

El primer arranque requiere red; los datos sobreviven al reemplazo de contenedores. Los volúmenes deben respaldarse y no se eliminan en el apagado habitual. La preparación local no acredita despliegue cloud ni disponibilidad de producción.

## Comprobación

CI construye imágenes y ejecuta pruebas, integración y comprobaciones documentales. El arranque local verifica servicios saludables y el circuito por CLI. Las mediciones se registran con versiones, datos y recursos.

GitHub Actions ejecuta análisis estático y unitarias por separado de la integración con servicios reales. Se comparó ejecutar comprobaciones manuales, un servidor de CI propio y un workflow versionado junto al código; se elige el workflow por su repetibilidad y menor operación local. Su presencia no acredita una ejecución remota: el equipo comprueba el resultado antes de entregar.
