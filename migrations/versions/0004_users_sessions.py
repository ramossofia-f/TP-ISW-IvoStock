"""Operadores individuales y sesiones de la aplicación (RF-01, RNF-11)."""

from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    op.execute(
        "CREATE TABLE users ("
        " id BIGSERIAL PRIMARY KEY,"
        " username TEXT NOT NULL UNIQUE CHECK(username ~ '^[a-z0-9][a-z0-9._-]{0,31}$'),"
        " password_hash TEXT NOT NULL,"
        " active BOOLEAN NOT NULL DEFAULT TRUE,"
        " created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        " last_login_at TIMESTAMPTZ)"
    )
    op.execute(
        "CREATE TABLE sessions ("
        " token_hash TEXT PRIMARY KEY,"
        " user_id BIGINT NOT NULL REFERENCES users ON DELETE CASCADE,"
        " created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        " expires_at TIMESTAMPTZ NOT NULL)"
    )
    op.execute("CREATE INDEX sessions_user ON sessions(user_id)")
    op.execute("CREATE INDEX sessions_expiry ON sessions(expires_at)")


def downgrade():
    op.execute("DROP TABLE sessions")
    op.execute("DROP TABLE users")
