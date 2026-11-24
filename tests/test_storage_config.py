"""Configuración de S3 para MinIO local y para AWS (ADR-0018), sin conectarse a ningún servicio."""

import pytest
from botocore.stub import Stubber

from ivostock.config import Settings
from ivostock.storage import Snapshots

BASE = {
    "DATABASE_URL": "postgresql+psycopg://u:p@db:5432/x",
    "SIMULATOR_TOKEN": "t",
    "SIMULATOR_ADMIN_TOKEN": "a",
    "S3_BUCKET": "ivostock-snapshots-prueba",
}


@pytest.fixture
def entorno(monkeypatch):
    for clave in ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_REGION"):
        monkeypatch.delenv(clave, raising=False)
    for clave, valor in BASE.items():
        monkeypatch.setenv(clave, valor)
    return monkeypatch


def test_minio_local_usa_endpoint_y_claves(entorno):
    entorno.setenv("S3_ENDPOINT", "http://minio:9000")
    entorno.setenv("S3_ACCESS_KEY", "clave")
    entorno.setenv("S3_SECRET_KEY", "secreto")
    cfg = Settings.from_env()
    assert (cfg.s3_endpoint, cfg.s3_access_key, cfg.s3_region) == (
        "http://minio:9000",
        "clave",
        "us-east-1",
    )
    assert Snapshots().client.meta.endpoint_url == "http://minio:9000"


def test_aws_sin_endpoint_ni_claves_usa_s3_y_las_credenciales_del_entorno(entorno):
    # Así queda el .env que genera `configurar.py --s3-bucket`.
    for clave in ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
        entorno.setenv(clave, "")
    entorno.setenv("S3_REGION", "sa-east-1")
    cfg = Settings.from_env()
    assert cfg.s3_endpoint is None and cfg.s3_access_key is None and cfg.s3_secret_key is None
    cliente = Snapshots().client
    assert cliente.meta.region_name == "sa-east-1"
    assert "amazonaws.com" in cliente.meta.endpoint_url


@pytest.mark.parametrize(
    "region,configuracion",
    [
        ("us-east-1", None),
        ("sa-east-1", {"LocationConstraint": "sa-east-1"}),
    ],
)
def test_crear_bucket_declara_la_region_fuera_de_us_east_1(entorno, region, configuracion):
    entorno.setenv("S3_REGION", region)
    snapshots = Snapshots()
    esperado = {"Bucket": BASE["S3_BUCKET"]}
    if configuracion:
        esperado["CreateBucketConfiguration"] = configuracion
    with Stubber(snapshots.client) as stub:
        stub.add_client_error("head_bucket", "404", http_status_code=404)
        stub.add_response("create_bucket", {}, esperado)
        snapshots.initialize()
        stub.assert_no_pending_responses()


def test_bucket_existente_no_se_vuelve_a_crear(entorno):
    snapshots = Snapshots()
    with Stubber(snapshots.client) as stub:
        stub.add_response("head_bucket", {}, {"Bucket": BASE["S3_BUCKET"]})
        snapshots.initialize()
        stub.assert_no_pending_responses()
