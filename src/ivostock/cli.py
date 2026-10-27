import argparse
import json
import os
import random
import time
from pathlib import Path

import httpx

from ivostock import services
from ivostock.config import Settings
from ivostock.db import database, rows
from ivostock.feed import parse, prepare
from ivostock.logs import configurar
from ivostock.publisher import publish_once


def parser():
    ap = argparse.ArgumentParser(description="Ivo Stock: operación del motor de inventario")
    commands = ap.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare", help="Preparar un original real sin encabezado")
    p.add_argument("source", type=Path)
    p.add_argument("directory", type=Path)
    p.add_argument("--provenance", required=True)
    p.add_argument("--captured-at", required=True)
    p = commands.add_parser("seed", help="Preparar catálogo estático del simulador")
    p.add_argument("store")
    p.add_argument("feed", type=Path)
    p.add_argument("--count", type=int, default=1000)
    p = commands.add_parser("provider-add")
    p.add_argument("name")
    p.add_argument("url")
    p = commands.add_parser("provider-disable")
    p.add_argument("provider", type=int)
    p = commands.add_parser("store-add", help="Incorporar una tienda e importar su catálogo")
    p.add_argument("store")
    p.add_argument(
        "--feed",
        type=Path,
        default=Path(os.getenv("CATALOG_FEED", "data/feeds/celesa.csv")),
        help="Inventario del que el simulador toma la muestra si la tienda no existe",
    )
    p.add_argument("--sample", type=float, default=0.5, help="Fracción de SKU distintos")
    p.add_argument("--wait", action="store_true", help="Importar en este proceso")
    p = commands.add_parser("ingest")
    p.add_argument("provider", type=int)
    p = commands.add_parser("replay")
    p.add_argument("run", type=int)
    p = commands.add_parser("suggest")
    p.add_argument("provider", type=int)
    p.add_argument("store")
    p.add_argument("--sku", help="Buscar coincidencias de un SKU exacto")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--positive-only", action="store_true")
    p = commands.add_parser("approve")
    p.add_argument("provider", type=int)
    p.add_argument("store")
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--items", nargs="+")
    selection.add_argument("--count", type=int)
    p.add_argument("--positive-only", action="store_true")
    for command in ("off", "resume"):
        p = commands.add_parser(command)
        p.add_argument("link", type=int)
    p = commands.add_parser("status")
    p.add_argument(
        "category",
        nargs="?",
        default="links",
        choices=["links", "providers", "stores", "runs", "quarantines", "deadletters", "tasks"],
    )
    p.add_argument("--store", help="Filtrar vínculos por tienda")
    p.add_argument("--summary", action="store_true", help="Contadores de vínculos")
    p.add_argument("--limit", type=int)
    p = commands.add_parser("schedule-now", help="Adelantar la próxima ingesta automática")
    p.add_argument("provider", type=int)
    p = commands.add_parser("monitor", help="Cuota, importación, vínculos e intentos")
    p.add_argument("--store")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=float, default=15)
    commands.add_parser("compare", help="Procesar los eventos disponibles")
    commands.add_parser("publish", help="Publicar una tarea disponible")
    p = commands.add_parser("fault", help="Provocar una falla en el simulador")
    p.add_argument("store")
    p.add_argument("status", type=int)
    p.add_argument("--item", default="*")
    p.add_argument("--remaining", type=int, default=1)
    return ap


def control(path, payload):
    cfg = Settings.from_env()
    response = httpx.post(
        cfg.simulator_url + path,
        json=payload,
        headers={"Authorization": "Bearer " + cfg.simulator_admin_token},
        timeout=120,
    )
    if response.status_code != 200:
        raise ValueError(f"Control rechazado: HTTP {response.status_code}")
    return response.json()


def control_get(path):
    cfg = Settings.from_env()
    response = httpx.get(
        cfg.simulator_url + path,
        headers={"Authorization": "Bearer " + cfg.simulator_admin_token},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def sample_catalog(store, feed, fraction):
    """Simplificación del POC: el simulador crea la tienda con una muestra del inventario."""
    if not 0 < fraction <= 1:
        raise ValueError("sample debe estar entre 0 y 1")
    if not feed.is_file():
        raise ValueError(f"No existe el inventario {feed} para preparar la tienda")
    skus = sorted(parse(feed.read_bytes()).stock)
    chosen = sorted(random.Random(store).sample(skus, int(len(skus) * fraction)))
    return [
        {"id": f"ITEM{n:06}", "sku": sku, "available_quantity": 0}
        for n, sku in enumerate(chosen, 1)
    ]


def add_store(engine, args):
    if not control_get(f"/admin/stores/{args.store}/summary")["exists"]:
        control(
            "/admin/seed",
            {"store": args.store, "items": sample_catalog(args.store, args.feed, args.sample)},
        )
    if args.wait:
        return services.add_store(engine, args.store)
    store = services.register_store(engine, args.store)
    return {
        "store": args.store,
        "status": "importing" if store["import_finished_at"] is None else store["status"],
        "catalog": "Importación en segundo plano; consultar con status stores",
    }


def monitor(engine, args):
    def snapshot():
        return services.monitor(
            engine,
            args.store,
            lambda store: control_get(f"/admin/stores/{store}/summary")["calls_last_minute"],
        )

    if not args.watch:
        return snapshot()
    try:
        while True:
            try:
                result = snapshot()
            except Exception as exc:  # Durante una caída de PostgreSQL el monitor sigue vivo.
                result = {"error": type(exc).__name__}
            print(json.dumps(result, ensure_ascii=False, default=str, indent=2), flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return {"monitor": "detenido"}


def run(args):
    if args.command == "prepare":
        return prepare(args.source, args.directory, args.provenance, args.captured_at)
    if args.command == "seed":
        stock = parse(args.feed.read_bytes()).stock
        if args.count < 1:
            raise ValueError("count debe ser positivo")
        items = [
            {"id": f"ITEM{n:06}", "sku": sku, "available_quantity": quantity}
            for n, (sku, quantity) in enumerate(sorted(stock.items())[: args.count], 1)
        ]
        return control("/admin/seed", {"store": args.store, "items": items})
    if args.command == "fault":
        return control(
            "/admin/fault",
            {
                "store": args.store,
                "item": args.item,
                "status": args.status,
                "remaining": args.remaining,
            },
        )
    engine = database()
    match args.command:
        case "provider-add":
            return services.add_provider(engine, args.name, args.url)
        case "provider-disable":
            return services.cut(engine, args.provider)
        case "store-add":
            return add_store(engine, args)
        case "ingest":
            return services.ingest(engine, args.provider)
        case "replay":
            with engine.begin() as conn:
                found = rows(conn, "SELECT provider_id FROM runs WHERE id=:r", r=args.run)
            if not found:
                raise ValueError("Corrida inexistente")
            return services.ingest(engine, found[0]["provider_id"], replay_of=args.run)
        case "suggest":
            found = services.suggestions(
                engine, args.provider, args.store, args.sku, args.positive_only
            )
            return {"total": len(found), "items": found[: args.limit]}
        case "approve":
            return services.approve(
                engine, args.provider, args.store, args.items, args.count, args.positive_only
            )
        case "off":
            with engine.begin() as conn:
                found = rows(conn, "SELECT provider_id FROM links WHERE id=:l", l=args.link)
            if not found:
                raise ValueError("Vínculo inexistente")
            return services.cut(engine, found[0]["provider_id"], args.link)
        case "resume":
            return services.resume(engine, args.link)
        case "status":
            return services.status(engine, args.category, args.store, args.summary, args.limit)
        case "schedule-now":
            return services.schedule_now(engine, args.provider)
        case "monitor":
            return monitor(engine, args)
        case "compare":
            count = 0
            while services.compare_once(engine):
                count += 1
            return {"events_processed": count}
        case "publish":
            return {"processed": publish_once(engine)}


def execute(args):
    """Devuelve (ok, resultado); los errores no exponen URL ni credenciales."""
    try:
        return True, run(args)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        return False, {"error": message}


def render(result):
    return json.dumps(result, ensure_ascii=False, default=str, indent=2)


def main():
    configurar()
    ok, result = execute(parser().parse_args())
    print(render(result) if ok else json.dumps(result, ensure_ascii=False))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
