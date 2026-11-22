#!/usr/bin/env bash
# Elimina todo lo que creó crear_entorno.sh: instancias, grupos de seguridad y buckets con la
# etiqueta Proyecto=ivostock. Los snapshots del bucket se borran: es un entorno de demostración.
#
#   scripts/aws/destruir_entorno.sh
set -euo pipefail
export AWS_REGION="${AWS_REGION:-us-east-1}"

INSTANCIAS="$(aws ec2 describe-instances \
  --filters Name=tag:Proyecto,Values=ivostock Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query 'Reservations[].Instances[].InstanceId' --output text)"
if [ -n "$INSTANCIAS" ]; then
  echo "Terminando instancias: $INSTANCIAS"
  aws ec2 terminate-instances --instance-ids $INSTANCIAS >/dev/null
  aws ec2 wait instance-terminated --instance-ids $INSTANCIAS
fi
for GRUPO in $(aws ec2 describe-security-groups --filters Name=tag:Proyecto,Values=ivostock \
  --query 'SecurityGroups[].GroupId' --output text); do
  echo "Borrando grupo de seguridad $GRUPO"
  aws ec2 delete-security-group --group-id "$GRUPO"
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
echo "Entorno de AWS eliminado."
