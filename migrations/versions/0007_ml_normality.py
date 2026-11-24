"""Observaciones durables y versiones inmutables del detector global de normalidad."""

from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade():
    op.execute("""
        CREATE TABLE ml_models (
            version TEXT PRIMARY KEY, payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
        );
        CREATE FUNCTION immutable_ml_model() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Las versiones ML son inmutables'; END $$;
        CREATE TRIGGER ml_models_immutable BEFORE UPDATE OR DELETE ON ml_models
            FOR EACH ROW EXECUTE FUNCTION immutable_ml_model();
        CREATE TABLE ml_state (
            id INTEGER PRIMARY KEY CHECK(id=1), active_version TEXT REFERENCES ml_models
        );
        INSERT INTO ml_state(id) VALUES(1);
        CREATE TABLE ml_observations (
            run_id BIGINT PRIMARY KEY REFERENCES runs,
            provider_id BIGINT NOT NULL REFERENCES providers,
            accepted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            features JSONB NOT NULL, trained_version TEXT REFERENCES ml_models,
            trained_at TIMESTAMPTZ, attempts INTEGER NOT NULL DEFAULT 0,
            retry_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(), last_error TEXT
        );
        CREATE INDEX ml_pending ON ml_observations(accepted_at,run_id)
            WHERE trained_version IS NULL;
        CREATE INDEX ml_provider_history ON ml_observations(provider_id,accepted_at DESC,run_id DESC);
    """)


def downgrade():
    op.execute("DROP TABLE ml_observations,ml_state,ml_models; DROP FUNCTION immutable_ml_model()")
