"""Genera configuración local sin sobrescribir secretos existentes."""

import secrets
from pathlib import Path

target = Path(".env")
if not target.exists():
    password = secrets.token_hex(24)
    values = {
        "POSTGRES_PASSWORD": password,
        "DATABASE_URL": f"postgresql+psycopg://ivostock:{password}@postgres:5432/ivostock",
        "S3_ENDPOINT": "http://minio:9000",
        "S3_ACCESS_KEY": secrets.token_hex(12),
        "S3_SECRET_KEY": secrets.token_hex(24),
        "S3_BUCKET": "snapshots",
        "SIMULATOR_URL": "http://simulator:8001",
        "SIMULATOR_TOKEN": secrets.token_hex(24),
        "SIMULATOR_ADMIN_TOKEN": secrets.token_hex(24),
        "TASK_LEASE_SECONDS": "30",
    }
    target.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
Path("data/feeds").mkdir(parents=True, exist_ok=True)
print("Configuración local disponible en .env; los valores no se imprimen.")
