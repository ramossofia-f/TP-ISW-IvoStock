import math
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ivostock.config import Settings
from ivostock.db import database, execute, rows
from ivostock.quota import reserve

app = FastAPI(title="Marketplace simulado", version="0.1.0")


def authorize(authorization: Annotated[str, Header()] = ""):
    if not secrets.compare_digest(authorization, "Bearer " + Settings.from_env().simulator_token):
        raise HTTPException(401, "Credencial inválida")


def admin(authorization: Annotated[str, Header()] = ""):
    if not secrets.compare_digest(
        authorization, "Bearer " + Settings.from_env().simulator_admin_token
    ):
        raise HTTPException(401, "Credencial de control inválida")


def admit(store):
    engine = database()
    with engine.begin() as conn:
        if not rows(conn, "SELECT id FROM sim_stores WHERE id=:s", s=store):
            raise HTTPException(404, "Tienda inexistente")
    if wait := reserve(engine, store, simulator=True):
        raise HTTPException(429, "Cuota agotada", headers={"Retry-After": str(math.ceil(wait))})


@app.middleware("http")
async def business_quota(request, call_next):
    parts = request.url.path.split("/")
    if len(parts) >= 4 and parts[1] == "stores":
        try:
            await run_in_threadpool(admit, parts[2])
        except HTTPException as exc:
            return JSONResponse(
                {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
            )
    return await call_next(request)


def injected(store, item):
    with database().begin() as conn:
        rules = rows(
            conn,
            "SELECT * FROM sim_faults WHERE store_id=:s AND item_id IN (:i,'*') AND remaining!=0 ORDER BY (item_id=:i) DESC LIMIT 1 FOR UPDATE",
            s=store,
            i=item,
        )
        if rules:
            rule = rules[0]
            execute(
                conn,
                "UPDATE sim_faults SET remaining=CASE WHEN remaining>0 THEN remaining-1 ELSE remaining END WHERE store_id=:s AND item_id=:i",
                s=store,
                i=rule["item_id"],
            )
            return JSONResponse(
                {"detail": "Falla de ensayo"},
                status_code=rule["status"],
                headers={"Retry-After": "1"} if rule["status"] == 429 else {},
            )
    return None


def serialize(item):
    return {**dict(item), "status": "active" if item["available_quantity"] else "out_of_stock"}


@app.get("/health")
def health():
    with database().connect() as conn:
        execute(conn, "SELECT 1 FROM sim_stores LIMIT 1")
    return {"status": "ok"}


@app.get("/stores/{store}/items", dependencies=[Depends(authorize)])
def catalog(store: str, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    if response := injected(store, "*"):
        return response
    with database().begin() as conn:
        items = rows(
            conn,
            "SELECT * FROM sim_items WHERE store_id=:s ORDER BY id LIMIT :n OFFSET :o",
            s=store,
            n=limit + 1,
            o=offset,
        )
    return {
        "items": [serialize(item) for item in items[:limit]],
        "next_offset": offset + limit if len(items) > limit else None,
    }


class Quantity(BaseModel):
    available_quantity: int = Field(ge=0, le=2147483647, strict=True)


@app.put("/stores/{store}/items/{item}/stock", dependencies=[Depends(authorize)])
def update(store: str, item: str, payload: Quantity):
    if response := injected(store, item):
        return response
    with database().begin() as conn:
        result = rows(
            conn,
            "UPDATE sim_items SET available_quantity=:q,writes=writes+1,updated_at=clock_timestamp() WHERE store_id=:s AND id=:i RETURNING *",
            q=payload.available_quantity,
            s=store,
            i=item,
        )
        if not result:
            raise HTTPException(404, "Publicación inexistente")
    return serialize(result[0])


class SeedItem(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    sku: str = Field(min_length=1)
    available_quantity: int = Field(ge=0, le=2147483647)


class Seed(BaseModel):
    store: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    items: list[SeedItem]


@app.post("/admin/seed", dependencies=[Depends(admin)])
def seed(payload: Seed):
    with database().begin() as conn:
        if rows(conn, "SELECT id FROM sim_stores WHERE id=:s", s=payload.store):
            raise HTTPException(409, "La tienda ya tiene catálogo")
        execute(conn, "INSERT INTO sim_stores(id) VALUES (:s)", s=payload.store)
        for item in payload.items:
            execute(
                conn,
                "INSERT INTO sim_items(store_id,id,sku,available_quantity) VALUES (:s,:i,:sku,:q)",
                s=payload.store,
                i=item.id,
                sku=item.sku,
                q=item.available_quantity,
            )
    return {"store": payload.store, "items": len(payload.items)}


class Fault(BaseModel):
    store: str
    item: str = "*"
    status: int = Field(ge=400, le=599)
    remaining: int = Field(ge=-1)


@app.post("/admin/fault", dependencies=[Depends(admin)])
def fault(payload: Fault):
    with database().begin() as conn:
        execute(
            conn,
            "INSERT INTO sim_faults(store_id,item_id,status,remaining) VALUES (:s,:i,:c,:n) ON CONFLICT(store_id,item_id) DO UPDATE SET status=EXCLUDED.status,remaining=EXCLUDED.remaining",
            s=payload.store,
            i=payload.item,
            c=payload.status,
            n=payload.remaining,
        )
    return {"status": "configured"}


@app.get("/admin/stores/{store}", dependencies=[Depends(admin)])
def observe(store: str):
    """Observador de ensayos: no es una lectura de negocio ni consume su cuota."""
    with database().begin() as conn:
        return [
            serialize(item)
            for item in rows(conn, "SELECT * FROM sim_items WHERE store_id=:s ORDER BY id", s=store)
        ]
