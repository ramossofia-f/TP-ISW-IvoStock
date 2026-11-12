"""Genera configuración local sin sobrescribir secretos existentes.

Además precrea las cuentas de los operadores (RF-01): en `.env` quedan sólo sus hashes
(`OPERATOR_ACCOUNTS`) y las contraseñas en `data/operadores.txt`, que Git ignora. Si las
cuentas ya existen no se regeneran; para rotarlas, borrar `OPERATOR_ACCOUNTS` de `.env` y
volver a ejecutar este script.
"""

import hashlib
import os
import secrets
from pathlib import Path

OPERATORS = [f"operador{n}" for n in range(1, 6)]
ITERATIONS = 200_000


def password_hash(password, salt, iterations=ITERATIONS):
    """Mismo formato que `ivostock.auth.password_hash`; este script sólo usa la biblioteca estándar."""
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256:{iterations}:{salt}:{digest.hex()}"


def new_operators():
    """Devuelve (valor de OPERATOR_ACCOUNTS, {usuario: contraseña})."""
    passwords = {name: secrets.token_urlsafe(12) for name in OPERATORS}
    accounts = ",".join(
        f"{name}={password_hash(password, secrets.token_hex(16))}"
        for name, password in passwords.items()
    )
    return accounts, passwords


def write_passwords(passwords, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(f"{name}: {password}\n" for name, password in passwords.items())
    # Se crea con permisos 0600: las contraseñas no deben quedar legibles por otros usuarios.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(lines)


def main():
    target = Path(".env")
    current = {}
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                current[key] = value
    password = current.get("POSTGRES_PASSWORD", secrets.token_hex(24))
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
        "SESSION_TTL_MINUTES": "480",
        "LOGIN_MAX_ATTEMPTS": "5",
        "LOGIN_WINDOW_MINUTES": "15",
        "MARKETPLACE_STORES": "T1,T2",
    }
    operators_created = "OPERATOR_ACCOUNTS" not in current
    if operators_created:
        values["OPERATOR_ACCOUNTS"], passwords = new_operators()
        write_passwords(passwords, Path("data/operadores.txt"))
    missing = {k: v for k, v in values.items() if k not in current}
    if missing:
        with target.open("a", encoding="utf-8") as handle:
            handle.write("".join(f"{k}={v}\n" for k, v in missing.items()))
    Path("data/feeds").mkdir(parents=True, exist_ok=True)
    print("Configuración local disponible en .env; los valores no se imprimen.")
    if operators_created:
        print("Operadores creados: usuarios y contraseñas en data/operadores.txt (fuera de Git).")


if __name__ == "__main__":
    main()
