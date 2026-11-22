#!/usr/bin/env bash
# Crea el entorno efímero de AWS para demostrar el despliegue (ADR-0018).
#
# Uso, desde la terminal del AWS Academy Learner Lab (trae la CLI con las credenciales de la
# sesión) o desde cualquier equipo con la CLI de AWS configurada:
#
#   scripts/aws/crear_entorno.sh IP_PUBLICA_DE_TU_EQUIPO
#
# Crea un bucket S3 privado para los snapshots, un grupo de seguridad que sólo admite SSH desde
# esa IP y una instancia EC2 con Docker que accede al bucket con el rol del laboratorio, sin
# claves. Todo queda etiquetado con Proyecto=ivostock para destruirlo con destruir_entorno.sh.
set -euo pipefail

IP="${1:?Indicar la IP pública desde la que se va a conectar por SSH (por ejemplo, curl https://checkip.amazonaws.com)}"
REGION="${AWS_REGION:-us-east-1}"
TIPO="${INSTANCE_TYPE:-t3.large}"
CLAVE="${KEY_NAME:-vockey}"
PERFIL="${INSTANCE_PROFILE:-LabInstanceProfile}"
CUENTA="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${S3_BUCKET:-ivostock-snapshots-${CUENTA}-$(date +%s)}"
ETIQUETA="Key=Proyecto,Value=ivostock"
export AWS_REGION="$REGION"

echo "Bucket privado para snapshots: $BUCKET"
if [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$BUCKET" >/dev/null
else
  aws s3api create-bucket --bucket "$BUCKET" \
    --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging "TagSet=[{$ETIQUETA}]"

echo "Grupo de seguridad: sólo SSH desde $IP/32; la aplicación no se expone a internet"
VPC="$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)"
GRUPO="$(aws ec2 create-security-group --group-name "ivostock-$(date +%s)" \
  --description "Ivo Stock: solo SSH" --vpc-id "$VPC" \
  --tag-specifications "ResourceType=security-group,Tags=[{$ETIQUETA}]" \
  --query GroupId --output text)"
aws ec2 authorize-security-group-ingress --group-id "$GRUPO" \
  --protocol tcp --port 22 --cidr "$IP/32" >/dev/null

AMI="$(aws ssm get-parameter \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query Parameter.Value --output text)"
INICIO="$(mktemp)"
cat > "$INICIO" <<'SCRIPT'
#!/bin/bash
set -euxo pipefail
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL -o /usr/local/lib/docker/cli-plugins/docker-compose \
  https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
SCRIPT

echo "Instancia $TIPO con Amazon Linux 2023, Docker y el rol $PERFIL"
INSTANCIA="$(aws ec2 run-instances --image-id "$AMI" --instance-type "$TIPO" \
  --key-name "$CLAVE" --security-group-ids "$GRUPO" \
  --iam-instance-profile "Name=$PERFIL" --user-data "file://$INICIO" \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --tag-specifications "ResourceType=instance,Tags=[{$ETIQUETA},{Key=Name,Value=ivostock}]" \
  --query 'Instances[0].InstanceId' --output text)"
rm -f "$INICIO"
aws ec2 wait instance-running --instance-ids "$INSTANCIA"
HOST="$(aws ec2 describe-instances --instance-ids "$INSTANCIA" \
  --query 'Reservations[0].Instances[0].PublicDnsName' --output text)"

cat <<FIN

Entorno creado:
  instancia  $INSTANCIA
  host       $HOST
  bucket     $BUCKET
  región     $REGION

Siguiente paso, desde la raíz del repo en tu equipo (con la clave labsuser.pem del lab):
  scripts/aws/desplegar.sh $HOST $BUCKET RUTA/labsuser.pem --verificar
FIN
