"""Genera configuración local sin sobrescribir secretos existentes."""

import hashlib
import secrets
from pathlib import Path

target = Path(".env")
current = {}
if target.exists():
    for line in target.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            current[key] = value
password = current.get("POSTGRES_PASSWORD", secrets.token_hex(24))
salt = secrets.token_hex(16)
# Cuenta de demostración del POC (Admin/Admin); en el entorno sólo queda su hash.
demo_hash = hashlib.pbkdf2_hmac("sha256", b"Admin", bytes.fromhex(salt), 200_000).hex()
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
    "CATALOG_FEED": "data/feeds/celesa.csv",
    "DEMO_USERNAME": "Admin",
    "DEMO_PASSWORD_HASH": f"pbkdf2_sha256$200000${salt}${demo_hash}",
}
missing = {k: v for k, v in values.items() if k not in current}
if missing:
    with target.open("a", encoding="utf-8") as handle:
        handle.write("".join(f"{k}={v}\n" for k, v in missing.items()))
Path("data/feeds").mkdir(parents=True, exist_ok=True)
print("Configuración local disponible en .env; los valores no se imprimen.")
