import os
import subprocess

from ivostock import auth
from ivostock.db import database
from ivostock.storage import Snapshots

subprocess.run(["alembic", "upgrade", "head"], check=True)
Snapshots().initialize()
operators = os.getenv("OPERATOR_ACCOUNTS", "")
if operators:
    print("Operadores:", auth.sync_operators(database(), operators))
else:
    print(
        "Sin OPERATOR_ACCOUNTS: nadie podrá iniciar sesión. Ejecutar python scripts/configurar.py"
    )
print("Esquema y bucket disponibles")
