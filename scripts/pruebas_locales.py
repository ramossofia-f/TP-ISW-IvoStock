"""Ejecuta integración en ivostock_test contra PostgreSQL y MinIO de Compose."""

import os
import subprocess
import sys
from pathlib import Path

for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        os.environ[key] = value
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace("@postgres:", "@127.0.0.1:")
os.environ["S3_ENDPOINT"] = "http://127.0.0.1:9000"
os.environ["RUN_INTEGRATION"] = "1"
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]]))
