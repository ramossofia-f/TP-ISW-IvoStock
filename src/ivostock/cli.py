import argparse
import json
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
    p = commands.add_parser("store-add")
    p.add_argument("store")
    p = commands.add_parser("ingest")
    p.add_argument("provider", type=int)
    p = commands.add_parser("replay")
    p.add_argument("run", type=int)
    p = commands.add_parser("suggest")
    p.add_argument("provider", type=int)
    p.add_argument("store")
    p.add_argument("--sku", help="Buscar coincidencias de un SKU exacto")
    p = commands.add_parser("approve")
    p.add_argument("provider", type=int)
    p.add_argument("store")
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--items", nargs="+")
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
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(f"Control rechazado: HTTP {response.status_code}")
    return response.json()


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
            return services.add_store(engine, args.store)
        case "ingest":
            return services.ingest(engine, args.provider)
        case "replay":
            with engine.begin() as conn:
                found = rows(conn, "SELECT provider_id FROM runs WHERE id=:r", r=args.run)
            if not found:
                raise ValueError("Corrida inexistente")
            return services.ingest(engine, found[0]["provider_id"], replay_of=args.run)
        case "suggest":
            return [
                dict(r) for r in services.suggestions(engine, args.provider, args.store, args.sku)
            ]
        case "approve":
            return services.approve(engine, args.provider, args.store, args.items)
        case "off":
            with engine.begin() as conn:
                found = rows(conn, "SELECT provider_id FROM links WHERE id=:l", l=args.link)
            if not found:
                raise ValueError("Vínculo inexistente")
            return services.cut(engine, found[0]["provider_id"], args.link)
        case "resume":
            return services.resume(engine, args.link)
        case "status":
            return services.status(engine, args.category)
        case "compare":
            count = 0
            while services.compare_once(engine):
                count += 1
            return {"events_processed": count}
        case "publish":
            return {"processed": publish_once(engine)}


def main():
    configurar()
    args = parser().parse_args()
    try:
        result = run(args)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(json.dumps({"error": message}, ensure_ascii=False))
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
