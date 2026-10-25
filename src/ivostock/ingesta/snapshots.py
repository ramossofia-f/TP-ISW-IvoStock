"""Snapshots crudos e inmutables de cada corrida (RF-20, ADR-0005)."""

from datetime import datetime
from typing import Protocol

from ivostock.config import requerida


class SnapshotExistente(Exception):
    """Se intentó sobrescribir un snapshot: nunca se permite."""


def clave(proveedor_id: str, corrida_id: str, iniciada: datetime) -> str:
    return f"{proveedor_id}/{iniciada:%Y/%m/%d}/{corrida_id}.raw"


class AlmacenSnapshots(Protocol):
    def guardar(self, clave: str, contenido: bytes, sha256: str) -> None: ...

    def leer(self, clave: str) -> bytes: ...


class AlmacenMemoria:
    """Implementación en memoria para tests."""

    def __init__(self) -> None:
        self.objetos: dict[str, bytes] = {}

    def guardar(self, clave: str, contenido: bytes, sha256: str) -> None:
        if clave in self.objetos:
            raise SnapshotExistente(clave)
        self.objetos[clave] = contenido

    def leer(self, clave: str) -> bytes:
        return self.objetos[clave]


class AlmacenS3:
    """Almacenamiento compatible con S3: MinIO en local, cualquier proveedor S3 en la nube."""

    def __init__(self) -> None:
        import boto3
        from botocore.exceptions import ClientError

        self._error = ClientError
        self.bucket = requerida("S3_BUCKET")
        self.cliente = boto3.client(
            "s3",
            endpoint_url=requerida("S3_ENDPOINT"),
            aws_access_key_id=requerida("S3_ACCESS_KEY"),
            aws_secret_access_key=requerida("S3_SECRET_KEY"),
        )
        try:
            self.cliente.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.cliente.create_bucket(Bucket=self.bucket)

    def guardar(self, clave: str, contenido: bytes, sha256: str) -> None:
        try:
            self.cliente.head_object(Bucket=self.bucket, Key=clave)
        except self._error:
            self.cliente.put_object(
                Bucket=self.bucket, Key=clave, Body=contenido, Metadata={"sha256": sha256}
            )
            return
        raise SnapshotExistente(clave)

    def leer(self, clave: str) -> bytes:
        return self.cliente.get_object(Bucket=self.bucket, Key=clave)["Body"].read()
