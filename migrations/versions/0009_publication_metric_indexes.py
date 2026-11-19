"""Índices de las expresiones usadas por la ventana y la retención de métricas."""

from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade():
    op.execute("DROP INDEX publication_measurements_window")
    # La ventana se filtra para todas las tiendas antes de agrupar por store_id.
    op.execute(
        "CREATE INDEX publication_measurements_window "
        "ON publication_measurements ((COALESCE(origin_at, recorded_at)))"
    )
    op.execute(
        "CREATE INDEX publication_measurements_retention "
        "ON publication_measurements ((COALESCE(confirmed_at, superseded_at)))"
    )


def downgrade():
    op.execute("DROP INDEX publication_measurements_retention, publication_measurements_window")
    op.execute(
        "CREATE INDEX publication_measurements_window "
        "ON publication_measurements (store_id, recorded_at)"
    )
