from contextlib import contextmanager
from functools import cache

from sqlalchemy import create_engine, text

from ivostock.config import Settings


def database():
    return _database(Settings.from_env().database_url)


@cache
def _database(url):
    return create_engine(url, pool_pre_ping=True)


def rows(conn, sql, **params):
    return list(conn.execute(text(sql), params).mappings())


def execute(conn, sql, **params):
    return conn.execute(text(sql), params)


@contextmanager
def ownership(engine, name):
    """Bloqueo de sesión: se libera también al morir el proceso propietario."""
    with engine.connect() as conn:
        acquired = conn.scalar(
            text("SELECT pg_try_advisory_lock(hashtextextended(:name, 0))"), {"name": name}
        )
        conn.commit()
        try:
            yield conn if acquired else None
        finally:
            if acquired:
                conn.rollback()
                conn.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:name, 0))"),
                    {"name": name},
                )
                conn.commit()
