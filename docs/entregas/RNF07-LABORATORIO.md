# Campaña RNF-07 en el laboratorio

Preparación solicitada el 19/11/2026. Inicio límite: 22/11/2026, hora de Buenos Aires.
Equipo propuesto: `fortega@labs004.udesa.edu.ar`. **La campaña todavía no se inició.**
La conexión SSH desde la sesión de preparación respondió `Permission denied (publickey,password)`;
Docker, permisos y persistencia del laboratorio deben verificarse desde una sesión autenticada.

El usuario indicó un apagado diario de 07:00 a 08:00 y autorizó medir 24 horas de reloj incluyendo
los cortes. Una hora completa sin muestras deja como máximo 1.380/1.440 = 95,83 % para API y
motor, por debajo del 99 % requerido. El resultado debe conservar esa indisponibilidad. Una
ejecución terminada y un requisito cumplido se informan por separado.

## Instrucciones para el agente que trabaja en el laboratorio

1. Inspeccionar el repositorio y las instrucciones locales. Usar una copia aislada de la última
   `origin/feat/metricas-disponibilidad`, que incorpora el último #18. Conservar el orden de
   integración #18 → #19 y las ramas con trabajo previo.
2. Verificar `hostname`, `date -Is`, `docker version`, `docker compose version`, acceso al daemon
   y `systemctl is-enabled docker`. Comprobar que el directorio de trabajo y los volúmenes
   sobreviven al apagado diario y que el equipo no se reinstala al arrancar. Si faltan Docker,
   permisos o persistencia, informar el impedimento antes de afirmar que empezó la campaña.
3. Elegir un `COMPOSE_PROJECT_NAME` propio y puertos libres. Ejecutar `python3 scripts/configurar.py`.
   Conservar `.env`, `data/` y ambos volúmenes; las credenciales y los datos crudos quedan fuera
   de Git. Preparar el feed archivado de Celesa si está disponible. Si se usa el generador,
   identificar explícitamente la carga sintética en la evidencia.
4. Seguir el README para levantar el stack, aprovisionar T1/T2, incorporarlas y aprobar vínculos.
   Registrar fuente, cantidades y carga elegidas. El ensayo de disponibilidad observa operación
   normal; las pruebas de capacidad ya tienen evidencia en #21 y #25. Completar la preparación
   y el drenaje antes de fijar la ventana.
5. Confirmar que API, proveedor, simulador, métricas y los cuatro workers están disponibles.
   Comprobar que Docker arranca al iniciar el equipo y que los servicios persistentes tienen
   política `unless-stopped`, como establece Compose. La recuperación debe funcionar sin una
   sesión SSH abierta. Si hace falta modificar la configuración del laboratorio con permisos
   administrativos, resolverlo con su responsable; la prueba no presupone esos permisos.
6. Construir la imagen de `cli` y fijar una única ventana con el comando de abajo. El comando
   exige una muestra reciente y los componentes disponibles; el archivo se crea exclusivamente
   una vez. Registrar también sistema operativo, CPU/RAM asignados y revisión medida.

```sh
docker compose up --build -d --wait
docker compose build cli
docker compose run --rm -T cli python scripts/medir_disponibilidad.py start \
  --revision "$(git rev-parse HEAD)" \
  --machine labs004.udesa.edu.ar \
  --note "24 horas de reloj; apagado diario previsto 07:00–08:00 America/Argentina/Buenos_Aires"
```

El archivo `data/evidencia/rnf07-campana.json` guarda inicio UTC en el próximo minuto completo,
fin exactamente 24 horas después, 1.440 posiciones, equipo y revisión. Comunicar al usuario
esas horas también en Buenos Aires y comprobar que el inicio respeta el 22/11.

## Corte diario y exportación

`metrics` conserva la serie en PostgreSQL; no depende de mantener este comando ni SSH abiertos.
Al volver la máquina, los servicios deben reanudarse sobre los mismos volúmenes. El archivo de
campaña conserva su ventana original: no volver a ejecutar `start`, extender el fin, descontar
el apagado ni rellenar minutos. PostgreSQL y métricas detenidos dejan posiciones faltantes,
que el resumen cuenta como no exitosas. La tolerancia de heartbeat del motor sigue siendo
660 segundos, según el protocolo del ADR-0017; esta campaña no la redefine.

Después del fin guardado, ejecutar el siguiente comando, aunque sea después del siguiente
arranque. Exportar antes de que venza la retención de siete días.

```sh
docker compose run --rm -T cli python scripts/medir_disponibilidad.py report
```

El comando usa las fechas originales y guarda
`data/evidencia/rnf07-campana-resultado.json`: metadatos, resumen, histórico disponible y resultado
del umbral para API y motor por separado. Rechaza una exportación anticipada y no sobrescribe
evidencia existente. No altera el muestreo, los feeds, las sesiones ni el estado operativo.

Conservar ambos JSON fuera de Git y redactar después un resumen versionable con las horas,
revisión, entorno, muestras esperadas/registradas/faltantes, cortes y porcentajes reales. El
resultado de disponibilidad interna sigue el protocolo del #19: no demuestra una sonda funcional
externa ni que un observador independiente haya estado disponible durante el corte.
