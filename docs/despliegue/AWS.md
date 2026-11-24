# Despliegue efímero en AWS

Demostración de readiness cloud del [ADR-0018](../adr/0018-despliegue-cloud-efimero.md): el mismo
`docker-compose.yml` que se usa en local, en una instancia EC2, con los snapshots en un bucket de
S3 real. Es un entorno de demostración que se crea, se verifica y se destruye; la corrección del
TP sigue siendo en local, según el [README](../../README.md#arranque).

## Qué se despliega

| Recurso | Para qué | Seguridad |
|---|---|---|
| Bucket S3 `ivostock-snapshots-…` | Snapshots inmutables (ADR-0003), en lugar de MinIO | Acceso público bloqueado |
| Rol de IAM `ivostock-…` | Credenciales temporales de la instancia para S3 | Sólo puede leer y escribir en ese bucket; no hay claves en `.env` |
| Par de claves SSH `ivostock-…` | Acceso a la instancia | La clave privada queda en `data/aws/`, fuera de Git |
| Grupo de seguridad | Regla única de entrada: SSH | Sólo desde la IP de quien despliega; ningún puerto de la aplicación abierto |
| EC2 `t3.large` con Amazon Linux 2023 | Los doce servicios del stack con Docker Compose | La aplicación escucha en `127.0.0.1`; IMDSv2 obligatorio |

Todo queda etiquetado con `Proyecto=ivostock`. Una hora de demostración consume unos US$0,10
de la instancia, más unos pocos MB en S3, dentro del presupuesto de la cuenta temporal.

## Requisitos

- **Una cuenta temporal de AWS** del Innovation Sandbox de UdeSA: en el portal de acceso,
  aplicación *UdeSA SandBox* → *Request lease* → plantilla *Ing del Soft*. Requiere aprobación de
  la cátedra; cuando está activa, la cuenta aparece en la pestaña *Cuentas* del portal.
- **La CLI de AWS v2** con un perfil de esa cuenta. Con el portal de UdeSA (región `us-east-2`):

  ```sh
  aws configure sso    # URL de inicio: https://d-9a677ec212.awsapps.com/start, región us-east-2
  aws sso login --profile PERFIL
  ```

- Git, SSH y este repositorio en el commit que se quiere desplegar.

## Pasos

Desde la raíz del repo, con `AWS_PROFILE` apuntando a la cuenta temporal:

1. **Crear el entorno.** Toma la IP pública de este equipo para la regla de SSH y guarda los
   datos del entorno en `data/aws/entorno.env`:

   ```sh
   AWS_PROFILE=PERFIL scripts/aws/crear_entorno.sh
   ```

2. **Desplegar y verificar:**

   ```sh
   scripts/aws/desplegar.sh --verificar
   ```

   Espera a que la instancia termine de instalar Docker, copia el commit con `git archive` (sin
   datos locales ni `.env`), genera en la instancia un `.env` para S3 con
   `configurar.py --s3-bucket` y levanta el stack con
   `docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build -d --wait`. Con
   `--verificar` genera un feed sintético, incorpora la tienda T1, da de alta un proveedor,
   aprueba cien vínculos, ejecuta una ingesta y lista los snapshots del bucket.

3. **Usar la interfaz**, con el túnel que imprime el script:

   ```sh
   ssh -i data/aws/ivostock-….pem -N -L 8000:127.0.0.1:8000 -L 8004:127.0.0.1:8004 ec2-user@HOST
   ```

   La aplicación queda en <http://localhost:8000> y las cuentas de operador están en
   `ivostock/data/operadores.txt` de la instancia.

4. **Destruir todo:**

   ```sh
   AWS_PROFILE=PERFIL scripts/aws/destruir_entorno.sh
   ```

   Termina la instancia y borra el grupo de seguridad, el par de claves, el rol y el bucket con
   sus snapshots.

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

### Despliegue en el Innovation Sandbox del 22/11/2026

Cuenta temporal de UdeSA (plantilla "Ing del Soft"), región `us-east-2`, commit `cbeb3a8`. No se
registran el número de cuenta ni la IP del equipo.

- `crear_entorno.sh` creó el bucket privado, el rol con permiso sólo sobre ese bucket, el par de
  claves, una VPC propia y una instancia `t3.large` con Amazon Linux 2023. Las cuentas del
  sandbox no traen VPC por defecto, así que el script crea la suya desde el commit `9c82b38`.
- `desplegar.sh --verificar` levantó 11 servicios sanos: el stack completo menos MinIO. Corrió
  el recorrido con 10.000 SKU, la tienda T1, el proveedor, la aprobación de 100 vínculos y la
  ingesta. Resultado: corrida 1 `accepted`, decisión por reglas (`insufficient_history`) y
  snapshot de 168.193 bytes listado con `aws s3 ls` en el bucket.
- El `.env` de la instancia no tiene endpoint ni claves de S3: boto3 usa el rol.
- La instancia exige IMDSv2: un pedido sin token a la metadata devuelve 401.
- El bucket tiene las cuatro opciones de acceso público bloqueadas. El grupo de seguridad sólo
  admite el puerto 22 desde la IP del equipo.

El primer intento encontró un defecto que en local no se veía. La imagen no precompilaba el
bytecode, y como el venv es de root, cada proceso recompilaba las dependencias. En 2 vCPU los
healthchecks de `publish` y `catalog` superaban los 5 s de timeout. Con `UV_COMPILE_BYTECODE=1`
(commit `cbeb3a8`), importar `ivostock.db` pasó de 1,29 s a 0,14 s.

`destruir_entorno.sh` terminó la instancia y borró el grupo de seguridad, el par de claves, la
VPC, el rol y el bucket con sus snapshots. En la primera pasada la VPC no se borró porque
quedaba la tabla de rutas propia: la consulta que la buscaba no la encontraba. Se corrigió en el
mismo PR y la segunda pasada borró lo que faltaba. Después se comprobó en `us-east-1` y
`us-east-2` que no quedaban instancias, VPC, grupos, claves, volúmenes, IP elásticas, buckets ni
roles. La instancia estuvo prendida unos 50 minutos, con un costo estimado menor a USD 0,10.

### Ensayo local del 22/11/2026

Antes de tener la cuenta se ensayó el modo AWS en una Mac, sobre el commit `1fa63b7`. No
reemplaza la evidencia en AWS: prueba la configuración, no la red, IAM ni la instancia.

- `.env` generado con `configurar.py --s3-bucket ivostock-ensayo --s3-region us-east-2`, sin
  endpoint ni claves de S3.
- Stack levantado con `docker-compose.yml` y `docker-compose.aws.yml`. Un tercer archivo, sólo
  del ensayo, volvió a levantar MinIO. Las variables estándar `AWS_ENDPOINT_URL_S3`,
  `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` hicieron de rol de la instancia.
- Los 12 servicios quedaron sanos. Se ejecutó el recorrido de `--verificar`: feed de 10.000
  SKU, tienda T1, proveedor, aprobación de 100 vínculos e ingesta.
- Resultado: corrida `accepted`. La configuración leída en el contenedor tenía endpoint y
  claves en `None` y región `us-east-2`. Quedó un objeto de 168.193 bytes en el bucket, escrito
  por boto3 con la cadena de credenciales por defecto.
