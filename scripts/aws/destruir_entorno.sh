#!/usr/bin/env bash
# Elimina todo lo que creó crear_entorno.sh: instancias, grupos de seguridad, pares de claves,
# roles y buckets con la etiqueta Proyecto=ivostock. Los snapshots se borran: es un entorno de
# demostración.
#
#   AWS_PROFILE=PERFIL scripts/aws/destruir_entorno.sh
set -euo pipefail
if [ -f data/aws/entorno.env ]; then
  # shellcheck source=/dev/null
  source data/aws/entorno.env
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"

INSTANCIAS="$(aws ec2 describe-instances \
  --filters Name=tag:Proyecto,Values=ivostock Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query 'Reservations[].Instances[].InstanceId' --output text)"
if [ -n "$INSTANCIAS" ]; then
  echo "Terminando instancias: $INSTANCIAS"
  # shellcheck disable=SC2086  # varios ids separados por espacios
  aws ec2 terminate-instances --instance-ids $INSTANCIAS >/dev/null
  # shellcheck disable=SC2086
  aws ec2 wait instance-terminated --instance-ids $INSTANCIAS
fi
for GRUPO in $(aws ec2 describe-security-groups --filters Name=tag:Proyecto,Values=ivostock \
  --query 'SecurityGroups[].GroupId' --output text); do
  echo "Borrando grupo de seguridad $GRUPO"
  aws ec2 delete-security-group --group-id "$GRUPO"
done
for CLAVE in $(aws ec2 describe-key-pairs --filters Name=tag:Proyecto,Values=ivostock \
  --query 'KeyPairs[].KeyName' --output text); do
  echo "Borrando par de claves $CLAVE"
  aws ec2 delete-key-pair --key-name "$CLAVE"
  rm -f "data/aws/$CLAVE.pem"
done
for ROL in $(aws iam list-roles --query 'Roles[?starts_with(RoleName, `ivostock-`)].RoleName' --output text); do
  if aws iam list-role-tags --role-name "$ROL" \
    --query "Tags[?Key=='Proyecto' && Value=='ivostock'] | length(@)" --output text | grep -qx 1; then
    echo "Borrando rol y perfil de instancia $ROL"
    aws iam remove-role-from-instance-profile --instance-profile-name "$ROL" --role-name "$ROL" 2>/dev/null || true
    aws iam delete-instance-profile --instance-profile-name "$ROL" 2>/dev/null || true
    aws iam delete-role-policy --role-name "$ROL" --policy-name snapshots 2>/dev/null || true
    aws iam delete-role --role-name "$ROL"
  fi
done
for BUCKET in $(aws s3api list-buckets --query 'Buckets[].Name' --output text); do
  # Sólo los buckets etiquetados por crear_entorno.sh, aunque tengan otro nombre.
  if aws s3api get-bucket-tagging --bucket "$BUCKET" \
    --query "TagSet[?Key=='Proyecto' && Value=='ivostock'] | length(@)" --output text 2>/dev/null \
    | grep -qx 1; then
    echo "Vaciando y borrando el bucket $BUCKET"
    aws s3 rb "s3://$BUCKET" --force >/dev/null
  fi
done
rm -f data/aws/entorno.env
echo "Entorno de AWS eliminado."
