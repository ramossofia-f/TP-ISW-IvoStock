"""Sesión de usuario del POC: imita las acciones del futuro frontend.

El login se valida localmente contra una cuenta de demostración cuyo hash está en
el entorno. La API autenticada con `POST /auth/login` corresponde al MVP (RF-01).
"""

import getpass
import hashlib
import hmac
import json
import os
import shlex

from ivostock import cli
from ivostock.logs import configurar

USER_COMMANDS = {
    "store-add",
    "provider-add",
    "provider-disable",
    "suggest",
    "approve",
    "off",
    "resume",
    "status",
}
HELP = (
    "Comandos: login, logout, exit y, con sesión iniciada: "
    + ", ".join(sorted(USER_COMMANDS))
    + ". Ejemplo: status links --store T1 --summary"
)


def password_hash(password, salt, iterations=200_000):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify(username, password, env=os.environ):
    expected_user = env.get("DEMO_USERNAME", "")
    stored = env.get("DEMO_PASSWORD_HASH", "")
    try:
        _, iterations, salt, _ = stored.split("$")
        candidate = password_hash(password, salt, int(iterations))
    except ValueError:
        return False
    return hmac.compare_digest(username, expected_user) & hmac.compare_digest(candidate, stored)


class Session:
    def __init__(self, ask=input, ask_secret=getpass.getpass):
        self.user = None
        self.ask = ask
        self.ask_secret = ask_secret

    def handle(self, line):
        """Devuelve la respuesta en JSON, o None para terminar la sesión."""
        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            return {"error": str(exc)}
        if not tokens:
            return {}
        command = tokens[0]
        if command in ("exit", "quit"):
            return None
        if command == "help":
            return {"help": HELP}
        if command == "login":
            username = self.ask("Usuario: ")
            if not verify(username, self.ask_secret("Contraseña: ")):
                return {"status": "rejected", "error": "Usuario o contraseña incorrectos"}
            self.user = username
            return {"status": "authenticated", "demo_login": True}
        if command == "logout":
            self.user = None
            return {"status": "logged_out"}
        if command not in USER_COMMANDS:
            return {"error": f"Comando desconocido en la sesión de usuario: {command}"}
        if self.user is None:
            return {"error": "Iniciar sesión con login"}
        try:
            args = cli.parser().parse_args(tokens)
        except SystemExit:
            return {"error": "Argumentos inválidos; ver help"}
        return cli.execute(args)[1]


def main():
    configurar()
    session = Session()
    print(json.dumps({"session": "usuario", "help": HELP}, ensure_ascii=False))
    while True:
        try:
            line = input("usuario> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        result = session.handle(line)
        if result is None:
            break
        if result:
            print(cli.render(result), flush=True)


if __name__ == "__main__":
    main()
