"""Configuración por entorno; los secretos nunca forman parte de las salidas de CLI."""

import os
import re
from dataclasses import dataclass

STORE_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")


def parse_stores(value):
    """`T1, T2` -> ("T1", "T2"); falla ante un identificador inválido o repetido."""
    stores = tuple(part.strip() for part in (value or "").split(",") if part.strip())
    if not all(STORE_ID.fullmatch(s) for s in stores) or len(set(stores)) != len(stores):
        raise ValueError("MARKETPLACE_STORES mal formado")
    return stores


@dataclass(frozen=True)
class Settings:
    database_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    simulator_url: str
    simulator_token: str
    simulator_admin_token: str
    lease_seconds: int
    # Tiendas del marketplace para las que hay credenciales preconfiguradas (RF-05).
    marketplace_stores: tuple[str, ...] = ()

    @classmethod
    def from_env(cls):
        return cls(
            os.environ["DATABASE_URL"],
            os.environ["S3_ENDPOINT"],
            os.environ["S3_ACCESS_KEY"],
            os.environ["S3_SECRET_KEY"],
            os.getenv("S3_BUCKET", "snapshots"),
            os.getenv("SIMULATOR_URL", "http://simulator:8001"),
            os.environ["SIMULATOR_TOKEN"],
            os.environ["SIMULATOR_ADMIN_TOKEN"],
            int(os.getenv("TASK_LEASE_SECONDS", "30")),
            parse_stores(os.getenv("MARKETPLACE_STORES")),
        )
