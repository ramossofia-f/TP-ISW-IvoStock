"""Estado operativo por minuto y tiempos de publicación por revisión."""

from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade():
    # Los vínculos anteriores quedan sin fecha conocida; no se fabrica su antigüedad.
    op.execute("ALTER TABLE links ADD COLUMN created_at TIMESTAMPTZ")
    op.execute("ALTER TABLE links ALTER COLUMN created_at SET DEFAULT clock_timestamp()")
    op.execute("""
        CREATE TABLE metric_samples (
            minute TIMESTAMPTZ PRIMARY KEY,
            payload JSONB NOT NULL
        );
        CREATE TABLE publication_measurements (
            link_id BIGINT NOT NULL REFERENCES links ON DELETE CASCADE,
            revision BIGINT NOT NULL,
            store_id TEXT NOT NULL REFERENCES stores ON DELETE CASCADE,
            origin_at TIMESTAMPTZ,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            effect_at TIMESTAMPTZ,
            confirmed_at TIMESTAMPTZ,
            superseded_at TIMESTAMPTZ,
            PRIMARY KEY (link_id, revision)
        );
        CREATE INDEX publication_measurements_window
            ON publication_measurements (store_id, recorded_at);
        CREATE TABLE sim_publication_effects (
            store_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            work_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            effect_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (store_id, item_id, work_id),
            FOREIGN KEY (store_id, item_id) REFERENCES sim_items ON DELETE CASCADE
        );
        INSERT INTO publication_measurements (link_id, revision, store_id, origin_at)
        SELECT t.link_id, t.revision, l.store_id, r.finished_at
        FROM tasks t JOIN links l ON l.id=t.link_id LEFT JOIN runs r ON r.id=t.run_id;
    """)


def downgrade():
    op.execute("DROP TABLE sim_publication_effects, publication_measurements, metric_samples")
    op.execute("ALTER TABLE links DROP COLUMN created_at")
