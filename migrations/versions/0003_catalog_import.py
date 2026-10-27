"""Importación de catálogo en segundo plano, validación inicial y stock inicial por vínculo."""

from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    op.execute(
        "ALTER TABLE stores ADD COLUMN import_offset INTEGER NOT NULL DEFAULT 0,"
        " ADD COLUMN import_total INTEGER, ADD COLUMN import_finished_at TIMESTAMPTZ"
    )
    op.execute(
        "UPDATE stores SET import_finished_at=now(),"
        " import_offset=(SELECT count(*) FROM catalog c WHERE c.store_id=stores.id),"
        " import_total=(SELECT count(*) FROM catalog c WHERE c.store_id=stores.id)"
        " WHERE status!='importing'"
    )
    op.execute("ALTER TABLE links ADD COLUMN initial_confirmed INTEGER")
    op.execute("UPDATE links SET initial_confirmed=confirmed")
    op.execute(
        "ALTER TABLE links ALTER COLUMN initial_confirmed SET NOT NULL,"
        " ADD CHECK(initial_confirmed>=0)"
    )
    op.execute(
        "CREATE TABLE provider_preview ("
        " provider_id BIGINT NOT NULL REFERENCES providers, sku TEXT NOT NULL,"
        " quantity INTEGER NOT NULL CHECK(quantity>=0), PRIMARY KEY(provider_id,sku))"
    )


def downgrade():
    op.execute("DROP TABLE provider_preview")
    op.execute("ALTER TABLE links DROP COLUMN initial_confirmed")
    op.execute(
        "ALTER TABLE stores DROP COLUMN import_finished_at, DROP COLUMN import_total,"
        " DROP COLUMN import_offset"
    )
