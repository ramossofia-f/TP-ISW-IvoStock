# Despliegue efímero en AWS

Demostración de readiness cloud del [ADR-0018](../adr/0018-despliegue-cloud-efimero.md): el mismo
`docker-compose.yml` que se usa en local, en una instancia EC2, con los snapshots en un bucket de
S3 real. Es un entorno de demostración que se crea, se verifica y se destruye; la corrección del
TP sigue siendo en local, según el [README](../../README.md#arranque).

## Qué se despliega

| Recurso | Para qué | Seguridad |
|---|---|---|
| Bucket S3 `ivostock-snapshots-…` | Snapshots inmutables (ADR-0003), en lugar de MinIO | Acceso público bloqueado; la instancia accede con el rol del laboratorio, sin claves |
| EC2 `t3.large` con Amazon Linux 2023 | Los doce servicios del stack con Docker Compose | Sólo SSH desde la IP de quien despliega; la aplicación escucha en `127.0.0.1` |
| Grupo de seguridad | Regla única de entrada: SSH | Sin puertos de la aplicación abiertos a internet |

Todo queda etiquetado con `Proyecto=ivostock`. Una hora de demostración consume unos US$0,10
de crédito de la instancia, más el almacenamiento de unos pocos MB en S3.

## Requisitos

- Una sesión iniciada del **AWS Academy Learner Lab**. Su terminal trae la CLI de AWS con las
  credenciales de la sesión.
- La clave `labsuser.pem` del laboratorio (botón *AWS Details* → *Download PEM*) en el equipo
  desde el que se despliega, con permisos `chmod 400`.
- En ese equipo: Git, SSH y este repositorio en el commit que se quiere desplegar.

## Pasos

1. **Crear el entorno**, en la terminal del Learner Lab, con la IP pública del equipo que va a
   desplegar (se obtiene con `curl https://checkip.amazonaws.com` en ese equipo):

   ```sh
   git clone URL_DEL_REPO ivostock && cd ivostock
   scripts/aws/crear_entorno.sh IP_DEL_EQUIPO
   ```

   Al terminar imprime el host de la instancia, el bucket y el comando siguiente.

2. **Desplegar y verificar**, desde la raíz del repo en el equipo:

   ```sh
   scripts/aws/desplegar.sh HOST BUCKET RUTA/labsuser.pem --verificar
   ```

   Espera a que la instancia termine de instalar Docker, copia el commit con `git archive` (sin
   datos locales ni `.env`), genera en la instancia un `.env` para S3 con
   `configurar.py --s3-bucket` y levanta el stack con
   `docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build -d --wait`. Con
   `--verificar` genera un feed sintético, incorpora la tienda T1, da de alta un proveedor,
   aprueba cien vínculos, ejecuta una ingesta y lista los snapshots del bucket.

3. **Usar la interfaz**, con el túnel que imprime el script:

   ```sh
   ssh -i RUTA/labsuser.pem -N -L 8000:127.0.0.1:8000 -L 8004:127.0.0.1:8004 ec2-user@HOST
   ```

   La aplicación queda en <http://localhost:8000> y las cuentas de operador están en
   `ivostock/data/operadores.txt` de la instancia.

4. **Destruir todo**, en la terminal del Learner Lab:

   ```sh
   scripts/aws/destruir_entorno.sh
   ```

   Termina la instancia y borra el grupo de seguridad y el bucket con sus snapshots.

## Diferencias con el despliegue local

| | Local | AWS |
|---|---|---|
| Snapshots | MinIO en un contenedor | Bucket S3 real |
| Credenciales de S3 | Generadas en `.env` | Rol de la instancia; ninguna clave en `.env` |
| Resto de los servicios | Docker Compose | El mismo Docker Compose |
| Acceso | `localhost` | Túnel SSH |

Lo que no cambia es intencional: se demuestra el sistema que se entrega y se prueba en CI, no
una variante.

## Evidencia

Pendiente de ejecutar en AWS Academy. Se registrará aquí la salida de `desplegar.sh --verificar`
(servicios sanos, corrida aceptada y snapshot listado en el bucket) y la de
`destruir_entorno.sh`.
