"""Configuración por entorno; los secretos nunca forman parte de las salidas de CLI."""

import os
from dataclasses import dataclass


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
        )
