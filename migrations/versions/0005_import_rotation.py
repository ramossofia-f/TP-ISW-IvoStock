"""Rotación de la importación de catálogos entre tiendas (C3)."""

from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    # Última vez que el worker de catálogo atendió a la tienda: la menos reciente va primero.
    op.execute("ALTER TABLE stores ADD COLUMN import_served_at TIMESTAMPTZ")


def downgrade():
    op.execute("ALTER TABLE stores DROP COLUMN import_served_at")
