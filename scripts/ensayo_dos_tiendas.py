"""Ensayo de RNF-02 y RNF-15: dos tiendas sanas con 1.000 vínculos cada una.

Corre contra el stack de Compose ya levantado y con T1 y T2 aprovisionadas (ver README), con los
workers reales y la cuota real. Hace dos corridas del mismo proveedor y mide cada una por separado
con `publication_measurements`: la primera lleva los 2.000 vínculos de cero a la cantidad del
proveedor; la segunda sólo propaga las cantidades que el proveedor de ensayo permuta.

Uso, desde la raíz del repo y con el mismo `.env` que el stack:

    uv run python scripts/ensayo_dos_tiendas.py                         # feed sintético
    uv run python scripts/ensayo_dos_tiendas.py --base data/feeds/celesa.csv

Escribe el detalle en `data/evidencia/` (fuera de Git) y el resumen versionable en
`docs/entregas/`. Sale con código 1 si alguna tienda no cumple RNF-02 o quedan resultados sin
medir.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

P95_MAXIMO = 30 * 60
P99_MAXIMO = 60 * 60
VINCULOS_POR_TIENDA = 1000
MUESTRAS_MINIMAS = 3
ESPERA_MAXIMA = timedelta(minutes=90)


# --- Entorno ---------------------------------------------------------------------------------


def entorno():
    """Carga `.env` y apunta los clientes del host a los puertos publicados por Compose."""
    valores = {}
    for linea in Path(".env").read_text(encoding="utf-8").splitlines():
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            valores[clave] = valor
    os.environ.update(valores)
    url = urlsplit(valores["DATABASE_URL"])
    credenciales = url.netloc.rsplit("@", 1)[0]
    puerto = valores.get("POSTGRES_HOST_PORT", "5432")
    os.environ["DATABASE_URL"] = urlunsplit(
        url._replace(netloc=f"{credenciales}@127.0.0.1:{puerto}")
    )
    os.environ["SIMULATOR_URL"] = "http://127.0.0.1:8001"
    os.environ["S3_ENDPOINT"] = "http://127.0.0.1:9000"


def cli(*argumentos):
    """Comando de la CLI dentro de Docker, donde `http://provider:8081` resuelve."""
    salida = subprocess.run(
        ["docker", "compose", "run", "--rm", "-T", "cli", "ivostock", *argumentos],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(salida[salida.index("{") :])


def esperar(condicion, limite, descripcion, cada=10):
    fin = time.monotonic() + limite.total_seconds()
    while not (resultado := condicion()):
        if time.monotonic() >= fin:
            raise TimeoutError(f"Sin terminar después de {limite}: {descripcion}")
        time.sleep(cada)
    return resultado


# --- Recursos --------------------------------------------------------------------------------


class Recursos(threading.Thread):
    """Muestrea `docker stats` del proyecto mientras dura el ensayo (RNF-15)."""

    def __init__(self, cada=30):
        super().__init__(daemon=True)
        self.cada, self.muestras, self.detener = cada, {}, threading.Event()
        self.proyecto = os.environ.get("COMPOSE_PROJECT_NAME") or Path.cwd().name

    def run(self):
        while not self.detener.is_set():
            salida = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
            ).stdout
            for linea in salida.splitlines():
                fila = json.loads(linea)
                if fila["Name"].startswith(self.proyecto + "-"):
                    servicio = fila["Name"][len(self.proyecto) + 1 :].rsplit("-", 1)[0]
                    self.muestras.setdefault(servicio, []).append(
                        (float(fila["CPUPerc"].rstrip("%")), memoria_mib(fila["MemUsage"]))
                    )
            self.detener.wait(self.cada)

    def resumen(self):
        return {
            servicio: {
                "muestras": len(valores),
                "cpu_promedio_pct": round(sum(c for c, _ in valores) / len(valores), 1),
                "cpu_maximo_pct": round(max(c for c, _ in valores), 1),
                "memoria_maxima_mib": round(max(m for _, m in valores), 1),
            }
            for servicio, valores in sorted(self.muestras.items())
        }


def memoria_mib(uso):
    """`"12.5MiB / 7.6GiB"` → 12.5."""
    valor = uso.split("/")[0].strip()
    for sufijo, factor in (("GiB", 1024), ("MiB", 1), ("KiB", 1 / 1024), ("B", 1 / 1024**2)):
        if valor.endswith(sufijo):
            return float(valor[: -len(sufijo)]) * factor
    raise ValueError(f"Memoria sin unidad conocida: {uso}")


def maquina():
    info = json.loads(
        subprocess.run(
            ["docker", "info", "--format", "{{json .}}"], capture_output=True, text=True
        ).stdout
    )
    return {
        "sistema": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "docker": info.get("ServerVersion"),
        "cpus_docker": info.get("NCPU"),
        "memoria_docker_gib": round(info.get("MemTotal", 0) / 1024**3, 1),
    }


# --- Medición y veredicto ------------------------------------------------------------------


def veredicto(fila, esperadas=None):
    """Cumple RNF-02 si no queda nada sin medir y p95/p99 están bajo sus máximos."""
    motivos = []
    if fila["pending"]:
        motivos.append(f"{fila['pending']} pendientes")
    if fila["unknown_duration"]:
        motivos.append(f"{fila['unknown_duration']} sin duración verificable")
    if esperadas is not None and fila["samples"] != esperadas:
        motivos.append(f"{fila['samples']} muestras de {esperadas} esperadas")
    if fila["p95_seconds"] is None or fila["p95_seconds"] >= P95_MAXIMO:
        motivos.append("p95 fuera de objetivo")
    if fila["p99_seconds"] is None or fila["p99_seconds"] >= P99_MAXIMO:
        motivos.append("p99 fuera de objetivo")
    return {"cumple": not motivos, "motivos": motivos}


def medir(engine, tiendas, desde, hasta):
    from ivostock.metrics import publications

    with engine.begin() as conn:
        filas = {f["store_id"]: f for f in publications(conn, desde, hasta)}
    return {tienda: filas[tienda] for tienda in tiendas}


def drenada(engine, tiendas, desde):
    filas = medir(engine, tiendas, desde, datetime.now(UTC) + timedelta(minutes=1))
    return all(f["revisions"] and not f["pending"] for f in filas.values())


# --- Reporte ---------------------------------------------------------------------------------


def decimal(valor):
    return str(valor).replace(".", ",")


def minutos(segundos):
    return "—" if segundos is None else f"{segundos / 60:.1f}".replace(".", ",")


def reporte(datos):
    lineas = [
        "# Ensayo de dos tiendas (RNF-02 y RNF-15)",
        "",
        "Generado por `scripts/ensayo_dos_tiendas.py`. Mide desde la aceptación de la corrida hasta "
        "el primer efecto externo en el simulador, por revisión, con los workers reales y la cuota "
        "de 60 llamadas por minuto y tienda. Objetivo de RNF-02: p95 menor a 30 minutos y p99 "
        "menor a 60 en cada tienda.",
        "",
        f"Ejecutado el {datos['ejecutado'][:16].replace('T', ' ')} UTC. Fuente: {datos['fuente']}. "
        f"{len(datos['tiendas'])} tiendas con {VINCULOS_POR_TIENDA} vínculos cada una, "
        f"{len(datos['tiendas']) * VINCULOS_POR_TIENDA} en total.",
        "",
        "| Corrida | Tienda | Cambios publicados | p95 (min) | p99 (min) | Pendientes | Sin duración | RNF-02 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for corrida in datos["corridas"]:
        for tienda, fila in corrida["tiendas"].items():
            resultado = corrida["veredicto"][tienda]
            estado = (
                "cumple" if resultado["cumple"] else "no cumple: " + "; ".join(resultado["motivos"])
            )
            lineas.append(
                f"| {corrida['numero']} | {tienda} | {fila['samples']} | "
                f"{minutos(fila['p95_seconds'])} | {minutos(fila['p99_seconds'])} | "
                f"{fila['pending']} | {fila['unknown_duration']} | {estado} |"
            )
    lineas += [
        "",
        "La corrida 1 lleva todos los vínculos de cero a la cantidad del proveedor: es la carga "
        "máxima. La corrida 2 sólo propaga las cantidades que el proveedor de ensayo permuta en "
        "cada consulta. Las corridas se adelantaron con `schedule-now`; en operación normal se "
        "repiten cada 300 minutos.",
        "",
        "## Cambios por corrida",
        "",
        "| Corrida | SKU del feed | Cambios publicados | Duración hasta drenar (min) |",
        "|---|---:|---:|---:|",
        *(
            f"| {c['numero']} | {c['sku']} | {sum(f['samples'] for f in c['tiendas'].values())} | "
            f"{minutos(c['segundos_hasta_drenar'])} |"
            for c in datos["corridas"]
        ),
        "",
        "## Recursos",
        "",
        f"{datos['maquina']['sistema']}, Docker {datos['maquina']['docker']} con "
        f"{datos['maquina']['cpus_docker']} CPU y "
        f"{str(datos['maquina']['memoria_docker_gib']).replace('.', ',')} GiB compartidos entre "
        "todos los servicios, sin límites por contenedor. Muestras de `docker stats` cada 30 "
        "segundos durante todo el ensayo; se omiten los contenedores de un solo uso (`init` y los "
        f"de `docker compose run`), con menos de {MUESTRAS_MINIMAS} muestras.",
        "",
        "| Servicio | CPU promedio (%) | CPU máximo (%) | Memoria máxima (MiB) |",
        "|---|---:|---:|---:|",
        *(
            f"| `{s}` | {decimal(r['cpu_promedio_pct'])} | {decimal(r['cpu_maximo_pct'])} "
            f"| {decimal(r['memoria_maxima_mib'])} |"
            for s, r in datos["recursos"].items()
            if r["muestras"] >= MUESTRAS_MINIMAS
        ),
        "",
    ]
    return "\n".join(lineas)


# --- Ensayo ----------------------------------------------------------------------------------


def preparar_feed(base, identificador):
    from ivostock.generador.feeds import Parametros, generar

    destino = Path("data/feeds") / f"ensayo-{identificador}.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if base:
        contenido = base.read_bytes()
        fuente = (
            f"inventario real ({base.name}, SHA-256 `{hashlib.sha256(contenido).hexdigest()[:12]}`)"
        )
    else:
        contenido = generar(Parametros(semilla=7, skus=10_000)).encode()
        fuente = "feed sintético del generador (10.000 SKU, semilla 7)"
    destino.write_bytes(contenido)
    return destino, fuente


def corrida(engine, proveedor, tiendas, numero):
    from ivostock import services

    desde = datetime.now(UTC)
    anteriores = {r["id"] for r in services.status(engine, "runs")}
    services.schedule_now(engine, proveedor)
    nueva = esperar(
        lambda: [
            r
            for r in services.status(engine, "runs")
            if r["id"] not in anteriores
            and r["provider_id"] == proveedor
            and r["status"] != "running"
        ],
        timedelta(minutes=15),
        f"corrida {numero}",
    )[0]
    if nueva["status"] != "accepted":
        raise RuntimeError(f"La corrida {numero} terminó en {nueva['status']}")
    esperar(
        lambda: drenada(engine, tiendas, desde),
        ESPERA_MAXIMA,
        f"publicación de la corrida {numero}",
        30,
    )
    hasta = datetime.now(UTC) + timedelta(minutes=1)
    filas = medir(engine, tiendas, desde, hasta)
    esperadas = VINCULOS_POR_TIENDA if numero == 1 else None
    return {
        "numero": numero,
        "run_id": nueva["id"],
        "sku": nueva["metrics"].get("sku"),
        "segundos_hasta_drenar": (datetime.now(UTC) - desde).total_seconds(),
        "tiendas": filas,
        "veredicto": {t: veredicto(f, esperadas) for t, f in filas.items()},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--base", type=Path, help="Inventario real preparado; sin él, feed sintético")
    ap.add_argument("--tiendas", nargs=2, default=["T1", "T2"])
    ap.add_argument(
        "--reporte-desde",
        type=Path,
        help="Regenerar el resumen desde una evidencia JSON, sin ensayar",
    )
    args = ap.parse_args(argv)
    if args.reporte_desde:
        datos = json.loads(args.reporte_desde.read_text(encoding="utf-8"))
        sufijo = "CELESA" if "real" in datos["fuente"] else "SINTETICO"
        Path(f"docs/entregas/ENSAYO-DOS-TIENDAS-{sufijo}.md").write_text(
            reporte(datos), encoding="utf-8"
        )
        return
    entorno()
    from ivostock import services
    from ivostock.db import database

    engine = database()
    identificador = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    if services.status(engine, "tasks"):
        raise SystemExit("Hay tareas pendientes: el ensayo exige tiendas sin cola previa")
    for tienda in args.tiendas:
        if services.status(engine, "links", store=tienda, summary=True)["total"]:
            raise SystemExit(f"{tienda} ya tiene vínculos: usar un COMPOSE_PROJECT_NAME nuevo")
        services.incorporate_store(engine, tienda)
    archivo, fuente = preparar_feed(args.base, identificador)
    recursos = Recursos()
    recursos.start()
    try:
        proveedor = cli(
            "provider-add", f"Ensayo {identificador}", f"http://provider:8081/{archivo.name}"
        )["id"]
        esperar(
            lambda: all(
                s["catalog_imported"]
                for s in services.list_stores(engine)
                if s["id"] in args.tiendas
            ),
            timedelta(minutes=60),
            "importación de catálogos",
        )
        for tienda in args.tiendas:
            aprobados = services.approve(
                engine, proveedor, tienda, count=VINCULOS_POR_TIENDA, positive_only=True
            )
            if aprobados["approved"] != VINCULOS_POR_TIENDA:
                raise RuntimeError(f"{tienda}: {aprobados['approved']} vínculos aprobados")
        corridas = [corrida(engine, proveedor, args.tiendas, n) for n in (1, 2)]
    finally:
        recursos.detener.set()
        recursos.join(timeout=60)
    datos = {
        "ejecutado": datetime.now(UTC).isoformat(),
        "fuente": fuente,
        "tiendas": args.tiendas,
        "corridas": corridas,
        "maquina": maquina(),
        "recursos": recursos.resumen(),
    }
    evidencia = Path("data/evidencia") / f"ensayo-dos-tiendas-{identificador}.json"
    evidencia.parent.mkdir(parents=True, exist_ok=True)
    evidencia.write_text(
        json.dumps(datos, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    sufijo = "CELESA" if args.base else "SINTETICO"
    Path(f"docs/entregas/ENSAYO-DOS-TIENDAS-{sufijo}.md").write_text(
        reporte(datos), encoding="utf-8"
    )
    print(reporte(datos))
    cumple = all(v["cumple"] for c in corridas for v in c["veredicto"].values())
    sys.exit(0 if cumple else 1)


if __name__ == "__main__":
    main()
