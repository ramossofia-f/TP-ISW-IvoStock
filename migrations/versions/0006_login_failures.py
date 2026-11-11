"""Intentos de inicio de sesión fallidos, para limitar la fuerza bruta (RNF-11)."""

from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade():
    # El usuario se guarda tal como se intentó (truncado), exista o no la cuenta: así el bloqueo
    # no revela qué cuentas existen.
    op.execute(
        "CREATE TABLE login_failures ("
        " id BIGSERIAL PRIMARY KEY,"
        " username TEXT NOT NULL,"
        " at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    op.execute("CREATE INDEX login_failures_user_at ON login_failures(username, at)")


def downgrade():
    op.execute("DROP TABLE login_failures")
