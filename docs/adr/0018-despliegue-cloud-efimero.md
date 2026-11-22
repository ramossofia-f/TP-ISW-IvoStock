# ADR-0018: Despliegue efímero en AWS con el mismo Compose y S3 real

Estado: aceptado. Fecha: 22/11/2026.

## Contexto y alternativas

La consigna exige que el MVP esté listo para correr en infraestructura cloud, con readiness
demostrable aunque el servicio no quede hosteado, y automatización del despliegue. También pide
que el proyecto se corrija sin costos significativos: el mecanismo principal de corrección sigue
siendo levantarlo en local (RNF-13). El equipo dispone de créditos de AWS Academy, cuyo Learner
Lab da sesiones de duración limitada, un rol de instancia ya creado (`LabInstanceProfile`) y no
permite crear roles de IAM propios. Hasta acá el [ADR-0008](0008-contenedores-ci.md) sólo cubría
Compose local, con MinIO como reemplazo de S3. Se compararon cuatro alternativas:

- **No desplegar y documentar la readiness.** No cuesta nada, pero la consigna pide readiness
  demostrable: una afirmación sin ejecución no se puede verificar, y el criterio de validez
  interna exige que lo declarado sea verificable.
- **Servicios gestionados: ECS con Fargate, RDS para PostgreSQL y S3.** Es lo más parecido a una
  producción real y quita la operación de las máquinas. Pero cambia la topología que describen
  los ADR 0002 y 0008, exige definiciones de tareas, red, balanceador y secretos para una docena
  de servicios, RDS tarda en crearse y cuesta por hora aunque no se use, y en el Learner Lab sólo
  se pueden usar los roles predefinidos del laboratorio. No entra en el tiempo ni en el presupuesto del MVP.
- **Kubernetes administrado (EKS).** Agrega un plano de control pago y manifiestos para cada
  servicio; es una complejidad que no responde a ningún requisito del PRD.
- **Una instancia EC2 con el mismo `docker compose` y los snapshots en S3 real.** Reutiliza
  exactamente lo que se prueba en local y en CI, así que la readiness que se demuestra es la del
  sistema entregado y no la de otra variante. Pasar de MinIO a S3 ejercita el único servicio que
  el diseño ya trata como externo (ADR-0003). A cambio, PostgreSQL sigue en un contenedor de la
  misma máquina, no hay alta disponibilidad y la instancia es un punto único de falla.

## Decisión

Se despliega de forma efímera en una EC2, con el mismo `docker-compose.yml` combinado con
`docker-compose.aws.yml`, que no levanta MinIO. Los snapshots van a un bucket de S3 privado con
acceso público bloqueado.

- El código acepta S3 sin endpoint ni claves: `boto3` toma las credenciales del rol de la
  instancia, así que no hay claves de AWS en `.env`, en Git ni en la imagen. La región se
  configura con `S3_REGION`. `scripts/configurar.py --s3-bucket` genera ese `.env`.
- Los puertos siguen enlazados a `127.0.0.1` y el grupo de seguridad sólo admite SSH desde la IP
  de quien despliega. La interfaz y el monitoreo se usan por túnel SSH: la aplicación no queda
  expuesta a internet y no hace falta gestionar certificados.
- `scripts/aws/crear_entorno.sh` crea bucket, grupo de seguridad e instancia, todo etiquetado;
  `scripts/aws/desplegar.sh` copia el commit con `git archive`, levanta el stack y, con
  `--verificar`, recorre el circuito y comprueba el snapshot en S3;
  `scripts/aws/destruir_entorno.sh` elimina todo lo etiquetado.
- El job `despliegue` de la CI valida, sin credenciales, los scripts con `shellcheck`, el `.env`
  para S3 y la configuración combinada de Compose.

## Consecuencias

La demostración cuesta unos centavos de crédito por hora y se destruye al terminar; nada queda
encendido fuera de las demos. La readiness es demostrable y repetible con tres comandos, pero
no acredita alta disponibilidad: una instancia y PostgreSQL en contenedor son puntos únicos de
falla, como ya declara RNF-08. Escalar a producción implicaría RDS para PostgreSQL y servicios
separados por proceso; el diseño lo admite porque los procesos ya sólo comparten PostgreSQL y S3
(ADR-0002), pero no se implementa. Las mediciones de RNF siguen haciéndose en local: el Learner
Lab corta las sesiones y no sirve para ensayos largos como el de 24 horas.

## Comprobación

Tests unitarios de la configuración de S3 para MinIO y para AWS, incluida la creación del bucket
fuera de `us-east-1`. Job `despliegue` de la CI. Ejecución de los tres scripts en AWS Academy,
con la salida de `--verificar` y la lista de snapshots del bucket registradas en
[docs/despliegue/AWS.md](../despliegue/AWS.md).
