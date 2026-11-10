"""Autenticación de la API: login, logout y la dependencia que protege los demás endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ivostock import auth
from ivostock.api_errors import SafeRoute
from ivostock.api_models import ErrorOut
from ivostock.db import database

bearer = HTTPBearer(auto_error=False, description="Token devuelto por POST /auth/login")
router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    route_class=SafeRoute,
    responses={500: {"model": ErrorOut, "description": "Error interno; no se detalla la causa"}},
)
UNAUTHENTICATED = {401: {"model": ErrorOut, "description": "Sin sesión válida"}}


class Login(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=auth.MAX_PASSWORD)


def unauthenticated():
    # Mismo mensaje para token ausente, desconocido, vencido o revocado.
    return HTTPException(401, "No autenticado", headers={"WWW-Authenticate": "Bearer"})


def require_operator(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    """Dependencia de todo endpoint salvo `/health` y `POST /auth/login` (RNF-11)."""
    operator = auth.resolve_session(database(), credentials.credentials) if credentials else None
    if operator is None:
        raise unauthenticated()
    return operator


Operator = Annotated[dict, Depends(require_operator)]


@router.post(
    "/login",
    summary="Iniciar sesión",
    description="Devuelve un token para `Authorization: Bearer`. Usuario inexistente, inactivo o "
    "contraseña errónea producen la misma respuesta.",
    responses={401: {"model": ErrorOut, "description": "Usuario o contraseña incorrectos"}},
)
async def login(body: Login):
    engine = database()
    # PBKDF2 es costoso: se ejecuta fuera del bucle de eventos.
    user = await run_in_threadpool(auth.authenticate, engine, body.username, body.password)
    if user is None:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    session = await run_in_threadpool(auth.create_session, engine, user["id"])
    return {
        "token": session["token"],
        "token_type": "bearer",
        "expires_at": session["expires_at"],
        "username": user["username"],
    }


@router.post("/logout", summary="Cerrar sesión", responses=UNAUTHENTICATED)
def logout(
    operator: Operator, credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]
):
    auth.revoke_session(database(), credentials.credentials)
    return {"status": "logged_out"}


@router.get("/me", summary="Operador de la sesión actual", responses=UNAUTHENTICATED)
def me(operator: Operator):
    return {"username": operator["username"], "expires_at": operator["expires_at"]}
