"""Cuentas de operador y sesiones: compartidas por la API y la sesión `usuario>`.

Las contraseñas sólo existen como hash PBKDF2. Tras `LOGIN_MAX_ATTEMPTS` intentos fallidos de un
mismo usuario dentro de `LOGIN_WINDOW_MINUTES` el acceso se bloquea hasta que el más antiguo
salga de la ventana (ADR-0014). Los tokens de sesión son aleatorios y se
guardan como SHA-256, así que una copia de la base no permite reutilizarlos. Los operadores se
precrean desde `OPERATOR_ACCOUNTS` (ver `scripts/configurar.py`); no hay alta por la API.
"""

import hashlib
import hmac
import logging
import os
import re
import secrets
from functools import cache

from ivostock.db import execute, rows

log = logging.getLogger("ivostock.auth")

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000
USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}")
MAX_PASSWORD = 256
MAX_USERNAME = 64


class LoginBlocked(Exception):
    """Demasiados intentos fallidos; `retry_after` son los segundos que faltan."""

    def __init__(self, retry_after):
        super().__init__("Inicio de sesión bloqueado")
        self.retry_after = retry_after


def max_attempts():
    return max(1, int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")))


def window_minutes():
    return max(1, int(os.getenv("LOGIN_WINDOW_MINUTES", "15")))


def normalize(username):
    return username.strip().lower()


def password_hash(password, salt=None, iterations=ITERATIONS):
    """`pbkdf2_sha256:iteraciones:sal:resumen`, sin `$` para sobrevivir a la interpolación de .env."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"{ALGORITHM}:{iterations}:{salt}:{digest.hex()}"


def verify_password(password, stored):
    """Comparación en tiempo constante; un hash mal formado nunca autentica."""
    try:
        algorithm, iterations, salt, _ = stored.split(":")
        if algorithm != ALGORITHM or len(password) > MAX_PASSWORD:
            return False
        candidate = password_hash(password, salt, int(iterations))
    except ValueError:
        return False
    return hmac.compare_digest(candidate, stored)


@cache
def _dummy_hash():
    return password_hash("sin-cuenta", "00" * 16)


def blocked_seconds(conn, username):
    """Segundos de bloqueo vigentes para `username`; 0 si puede intentar."""
    found = rows(
        conn,
        "SELECT count(*) AS n,"
        " CEIL(EXTRACT(EPOCH FROM (min(at)+make_interval(mins=>:w)-now()))) AS wait"
        " FROM (SELECT at FROM login_failures WHERE username=:u"
        " AND at>now()-make_interval(mins=>:w) ORDER BY at DESC LIMIT :m) recent",
        u=username,
        w=window_minutes(),
        m=max_attempts(),
    )[0]
    return max(1, int(found["wait"])) if found["n"] >= max_attempts() else 0


def authenticate(engine, username, password):
    """Devuelve el operador o None. Usuario inexistente, inactivo o clave errónea son iguales.

    Con un usuario inexistente se verifica igualmente contra un hash ficticio para no revelar
    por tiempo de respuesta qué cuentas existen. Lanza `LoginBlocked` si el usuario acumuló
    demasiados fallos: el bloqueo vale también para cuentas inexistentes y no se extiende con los
    intentos hechos mientras dura. Los intentos del mismo usuario se serializan, de modo que
    probar claves en paralelo no supera el límite.
    """
    username = normalize(username)[:MAX_USERNAME]
    with engine.begin() as conn:
        execute(conn, "SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))", k=f"login:{username}")
        wait = blocked_seconds(conn, username)
        if wait:
            log.warning(
                "Inicio de sesión bloqueado", extra={"component": "auth", "status": "blocked"}
            )
            raise LoginBlocked(wait)
        found = rows(
            conn,
            "SELECT id,username,password_hash,active FROM users WHERE username=:u",
            u=username,
        )
        user = found[0] if found else None
        valid = verify_password(password, user["password_hash"] if user else _dummy_hash())
        if not (user and user["active"] and valid):
            execute(conn, "INSERT INTO login_failures(username) VALUES (:u)", u=username)
            execute(
                conn,
                "DELETE FROM login_failures WHERE at<=now()-make_interval(mins=>:w)",
                w=window_minutes(),
            )
            log.info(
                "Inicio de sesión rechazado", extra={"component": "auth", "status": "rejected"}
            )
            return None
        execute(conn, "DELETE FROM login_failures WHERE username=:u", u=username)
        execute(conn, "UPDATE users SET last_login_at=now() WHERE id=:i", i=user["id"])
    log.info("Inicio de sesión", extra={"component": "auth", "status": "ok", "user": username})
    return {"id": user["id"], "username": user["username"]}


def ttl_minutes():
    return int(os.getenv("SESSION_TTL_MINUTES", "480"))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(engine, user_id):
    token = secrets.token_urlsafe(32)
    with engine.begin() as conn:
        execute(conn, "DELETE FROM sessions WHERE expires_at<=now()")
        expires = rows(
            conn,
            "INSERT INTO sessions(token_hash,user_id,expires_at)"
            " VALUES (:h,:u,now()+make_interval(mins=>:m)) RETURNING expires_at",
            h=token_hash(token),
            u=user_id,
            m=ttl_minutes(),
        )[0]["expires_at"]
    return {"token": token, "expires_at": expires}


def resolve_session(engine, token):
    """Operador de una sesión vigente, o None si el token es desconocido, vencido o revocado."""
    if not token:
        return None
    with engine.begin() as conn:
        found = rows(
            conn,
            "SELECT u.id,u.username,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id"
            " WHERE s.token_hash=:h AND s.expires_at>now() AND u.active",
            h=token_hash(token),
        )
    return dict(found[0]) if found else None


def revoke_session(engine, token):
    with engine.begin() as conn:
        execute(conn, "DELETE FROM sessions WHERE token_hash=:h", h=token_hash(token))


def parse_operators(value):
    """`usuario=hash,usuario=hash` -> [(usuario, hash)]; rechaza entradas mal formadas."""
    accounts = []
    for entry in filter(None, (part.strip() for part in (value or "").split(","))):
        username, separator, stored = entry.partition("=")
        if not separator or not USERNAME.fullmatch(username) or stored.count(":") != 3:
            raise ValueError("OPERATOR_ACCOUNTS mal formado")
        accounts.append((username, stored))
    return accounts


def sync_operators(engine, value):
    """Precrea los operadores del entorno. Es idempotente y no toca a los demás usuarios.

    Si el hash cambió (se regeneró la cuenta en .env), se actualiza y se cierran sus sesiones.
    """
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    with engine.begin() as conn:
        for username, stored in parse_operators(value):
            found = rows(
                conn, "SELECT id,password_hash FROM users WHERE username=:u FOR UPDATE", u=username
            )
            if not found:
                execute(
                    conn,
                    "INSERT INTO users(username,password_hash) VALUES (:u,:h)",
                    u=username,
                    h=stored,
                )
                counts["created"] += 1
            elif found[0]["password_hash"] != stored:
                execute(
                    conn,
                    "UPDATE users SET password_hash=:h WHERE id=:i",
                    h=stored,
                    i=found[0]["id"],
                )
                execute(conn, "DELETE FROM sessions WHERE user_id=:i", i=found[0]["id"])
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1
    return counts
