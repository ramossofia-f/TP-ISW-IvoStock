#!/usr/bin/env bash
# Crea el entorno efímero de AWS para demostrar el despliegue (ADR-0018).
#
#   AWS_PROFILE=PERFIL scripts/aws/crear_entorno.sh [IP_PUBLICA]
#
# Se ejecuta desde la raíz del repo con un perfil de la CLI de AWS, por ejemplo el de la cuenta
# temporal del Innovation Sandbox de UdeSA (docs/despliegue/AWS.md). Sin IP, usa la pública de
# este equipo. Crea, todo etiquetado con Proyecto=ivostock:
#   - un bucket S3 privado para los snapshots;
#   - un rol de IAM para la instancia con permiso sólo sobre ese bucket, sin claves;
#   - un par de claves SSH, cuya parte privada queda en data/aws/ (fuera de Git);
#   - un grupo de seguridad que sólo admite SSH desde esa IP;
#   - una instancia EC2 con Docker.
# Los datos del entorno quedan en data/aws/entorno.env para desplegar.sh y destruir_entorno.sh.
set -euo pipefail

IP="${1:-$(curl -fsS https://checkip.amazonaws.com)}"
REGION="${AWS_REGION:-us-east-1}"
TIPO="${INSTANCE_TYPE:-t3.large}"
SUFIJO="$(date +%s)"
CUENTA="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${S3_BUCKET:-ivostock-snapshots-${CUENTA}-${SUFIJO}}"
NOMBRE="ivostock-${SUFIJO}"
ETIQUETA="Key=Proyecto,Value=ivostock"
DATOS="data/aws"
CLAVE="$DATOS/$NOMBRE.pem"
export AWS_REGION="$REGION"
mkdir -p "$DATOS"

echo "Cuenta $CUENTA, región $REGION"
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

echo "Rol de la instancia $NOMBRE: sólo lectura y escritura de s3://$BUCKET"
aws iam create-role --role-name "$NOMBRE" --tags "$ETIQUETA" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
aws iam put-role-policy --role-name "$NOMBRE" --policy-name snapshots --policy-document \
  "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:ListBucket\"],\"Resource\":\"arn:aws:s3:::$BUCKET\"},{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\"],\"Resource\":\"arn:aws:s3:::$BUCKET/*\"}]}"
aws iam create-instance-profile --instance-profile-name "$NOMBRE" --tags "$ETIQUETA" >/dev/null
aws iam add-role-to-instance-profile --instance-profile-name "$NOMBRE" --role-name "$NOMBRE"
aws iam wait instance-profile-exists --instance-profile-name "$NOMBRE"
sleep 10  # IAM es eventualmente consistente: EC2 puede no ver el perfil recién creado.

echo "Clave SSH en $CLAVE (fuera de Git)"
aws ec2 create-key-pair --key-name "$NOMBRE" --key-type ed25519 \
  --tag-specifications "ResourceType=key-pair,Tags=[{$ETIQUETA}]" \
  --query KeyMaterial --output text > "$CLAVE"
chmod 400 "$CLAVE"

echo "Grupo de seguridad: sólo SSH desde $IP/32; la aplicación no se expone a internet"
VPC="$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)"
GRUPO="$(aws ec2 create-security-group --group-name "$NOMBRE" \
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

echo "Instancia $TIPO con Amazon Linux 2023 y Docker"
INSTANCIA="$(aws ec2 run-instances --image-id "$AMI" --instance-type "$TIPO" \
  --key-name "$NOMBRE" --security-group-ids "$GRUPO" \
  --iam-instance-profile "Name=$NOMBRE" --user-data "file://$INICIO" \
  --metadata-options HttpTokens=required \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --tag-specifications "ResourceType=instance,Tags=[{$ETIQUETA},{Key=Name,Value=$NOMBRE}]" \
  --query 'Instances[0].InstanceId' --output text)"
rm -f "$INICIO"
aws ec2 wait instance-running --instance-ids "$INSTANCIA"
HOST="$(aws ec2 describe-instances --instance-ids "$INSTANCIA" \
  --query 'Reservations[0].Instances[0].PublicDnsName' --output text)"

cat > "$DATOS/entorno.env" <<FIN
AWS_REGION=$REGION
HOST=$HOST
BUCKET=$BUCKET
CLAVE=$CLAVE
INSTANCIA=$INSTANCIA
FIN

cat <<FIN

Entorno creado (datos en $DATOS/entorno.env):
  instancia  $INSTANCIA  ($TIPO)
  host       $HOST
  bucket     $BUCKET

Siguiente paso:
  AWS_PROFILE=${AWS_PROFILE:-PERFIL} scripts/aws/desplegar.sh --verificar
FIN
