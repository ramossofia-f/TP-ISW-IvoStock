#!/usr/bin/env bash
# Despliega el commit actual en la instancia de crear_entorno.sh (ADR-0018).
#
#   scripts/aws/desplegar.sh [--verificar]
#
# Lee host, bucket y clave de data/aws/entorno.env. Copia el árbol del commit con git archive
# (sin datos locales ni .env), genera en la instancia un .env para S3 real y levanta el mismo
# docker-compose.yml que en local, combinado con docker-compose.aws.yml. Con --verificar
# aprovisiona un feed sintético, recorre alta de tienda, proveedor, aprobación e ingesta, y
# comprueba que el snapshot quedó en el bucket.
set -euo pipefail

# shellcheck source=/dev/null
source data/aws/entorno.env
VERIFICAR="${1:-}"
SSH=(ssh -i "$CLAVE" -o StrictHostKeyChecking=accept-new "ec2-user@$HOST")
COMMIT="$(git rev-parse --short HEAD)"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.aws.yml"

echo "Esperando que la instancia termine de instalar Docker"
until "${SSH[@]}" -o ConnectTimeout=5 true 2>/dev/null; do sleep 5; done
"${SSH[@]}" "cloud-init status --wait >/dev/null"
echo "Copiando el commit $COMMIT"
git archive --format=tar HEAD | "${SSH[@]}" "rm -rf ivostock && mkdir ivostock && tar -x -C ivostock"
echo "Configurando y levantando el stack (los snapshots van a s3://$BUCKET)"
"${SSH[@]}" "cd ivostock && python3 scripts/configurar.py --s3-bucket $BUCKET --s3-region $AWS_REGION \
  && echo COMPOSE_PROJECT_NAME=ivostock >> .env \
  && $COMPOSE up --build -d --wait \
  && $COMPOSE ps --format '{{.Service}}: {{.State}} {{.Health}}'"

if [ "$VERIFICAR" = "--verificar" ]; then
  echo "Recorrido de punta a punta con un feed sintético"
  "${SSH[@]}" "cd ivostock && C='$COMPOSE run --rm -T cli' \
    && \$C python -m ivostock.generador.feeds --salida data/feeds/demo.csv --skus 10000 --semilla 7 \
    && \$C python scripts/provisionar_tiendas.py --feed data/feeds/demo.csv \
    && \$C ivostock store-add T1 --wait \
    && \$C ivostock provider-add Demo 'http://provider:8081/demo.csv?no-changes=true' \
    && \$C ivostock approve 1 T1 --count 100 --positive-only \
    && \$C ivostock ingest 1 \
    && \$C ivostock status runs \
    && echo 'Snapshots en S3:' && aws s3 ls s3://$BUCKET/sha256/ --region $AWS_REGION"
fi

cat <<FIN

Desplegado el commit $COMMIT en $HOST.
Para usar la interfaz y el monitoreo desde este equipo, abrir el túnel y entrar a
http://localhost:8000 con una cuenta de ivostock/data/operadores.txt de la instancia:
  ssh -i $CLAVE -N -L 8000:127.0.0.1:8000 -L 8004:127.0.0.1:8004 ec2-user@$HOST
  ssh -i $CLAVE ec2-user@$HOST cat ivostock/data/operadores.txt
FIN
