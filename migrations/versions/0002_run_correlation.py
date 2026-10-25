"""Correlación de corridas con trabajo e intentos."""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.execute("ALTER TABLE tasks ADD COLUMN run_id BIGINT REFERENCES runs")
    op.execute("ALTER TABLE attempts ADD COLUMN run_id BIGINT REFERENCES runs")


def downgrade():
    op.execute("ALTER TABLE attempts DROP COLUMN run_id")
    op.execute("ALTER TABLE tasks DROP COLUMN run_id")
