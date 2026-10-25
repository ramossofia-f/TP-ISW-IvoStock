import subprocess

from ivostock.storage import Snapshots

subprocess.run(["alembic", "upgrade", "head"], check=True)
Snapshots().initialize()
print("Esquema y bucket disponibles")
