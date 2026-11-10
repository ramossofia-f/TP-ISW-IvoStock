"""Sesión de usuario: imita las acciones del frontend.

El login usa las mismas cuentas de operador que la API (`POST /auth/login`, RF-01): se
verifica contra la tabla `users` con `ivostock.auth`.
"""

import getpass
import json
import shlex

from ivostock import auth, cli
from ivostock.db import database
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


class Session:
    def __init__(self, ask=input, ask_secret=getpass.getpass, engine=None):
        self.user = None
        self.engine = engine
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
            password = self.ask_secret("Contraseña: ")
            try:
                operator = auth.authenticate(self.engine or database(), username, password)
            except Exception as exc:  # Sin base no hay login; no se expone el detalle.
                return {
                    "status": "error",
                    "error": f"No se pudo verificar la cuenta ({type(exc).__name__})",
                }
            if operator is None:
                return {"status": "rejected", "error": "Usuario o contraseña incorrectos"}
            self.user = operator["username"]
            return {"status": "authenticated", "user": self.user}
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
