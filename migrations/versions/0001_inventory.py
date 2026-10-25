"""Estado, cola, cuota y simulador de inventario."""

from importlib.resources import files

from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    for statement in files("ivostock").joinpath("schema.sql").read_text().split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError("Restaurar un respaldo en una base nueva para volver de esquema")
