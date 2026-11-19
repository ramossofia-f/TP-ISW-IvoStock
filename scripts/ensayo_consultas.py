"""Ensayo de RNF-09: cinco operadores, una consulta por segundo cada uno, durante 30 minutos.

Corre contra el stack de Compose ya levantado y con al menos 2.000 vínculos, por ejemplo después
de `scripts/ensayo_dos_tiendas.py` en el mismo proyecto. Sigue el protocolo del SRD: 9.000
consultas autenticadas a la API, 50 % listados de cien vínculos, 25 % búsquedas de SKU y 25 %
corridas y fallas. El motor queda activo: se adelanta una ingesta al empezar y otra a la mitad.

La carga es abierta: cada consulta sale en su segundo programado aunque la anterior no haya
terminado, y la latencia se mide desde ese momento, de modo que una respuesta lenta no demora ni
oculta las siguientes. Un error o un timeout no se descarta: se informa y el ensayo no cumple.

Uso, desde la raíz del repo y con el mismo `.env` que el stack:

    uv run python scripts/ensayo_consultas.py --fuente sintetico
    uv run python scripts/ensayo_consultas.py --fuente celesa

Escribe el detalle en `data/evidencia/` (fuera de Git) y el resumen versionable en
`docs/entregas/`. Sale con código 1 si no cumple RNF-09.
"""

import argparse
import asyncio
import json
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from ensayo_comun import Recursos, decimal, entorno, invalido, maquina, seccion_recursos

OPERADORES = 5
MINUTOS = 30
P95_MAXIMO = 2.0
TIMEOUT = 10.0
API = "http://127.0.0.1:8000"
# Proporciones del protocolo del SRD; "corridas y fallas" se reparte en partes iguales.
PROPORCIONES = {"listado": 0.50, "sku": 0.25, "corridas": 0.125, "fallas": 0.125}
DESCRIPCION = {
    "listado": "`GET /links` de una tienda, cien vínculos desde un offset al azar",
    "sku": "`GET /providers/{id}/suggestions` con un SKU vinculado",
    "corridas": "`GET /runs`, las veinte corridas más recientes",
    "fallas": "`GET /links/summary` de una tienda: pendientes, fallidos y sincronizados",
}


# --- Plan --------------------------------------------------------------------------------------


def plan(semilla, operadores, segundos, tiendas, skus, proveedor, vinculos_por_tienda):
    """Lista de consultas `(segundo, operador, tipo, ruta, parámetros)`, determinista.

    Cada operador consulta una vez por segundo, desfasado una fracción de segundo del anterior.
    Las cantidades por tipo son exactas, no probabilísticas.
    """
    azar = random.Random(semilla)
    total = operadores * segundos
    tipos = []
    for tipo, proporcion in PROPORCIONES.items():
        tipos += [tipo] * round(total * proporcion)
    tipos = (tipos + ["listado"] * total)[:total]
    azar.shuffle(tipos)
    paginas = max(1, vinculos_por_tienda // 100)
    consultas = []
    for indice, tipo in enumerate(tipos):
        operador, segundo = indice % operadores, indice // operadores
        tienda = azar.choice(tiendas)
        if tipo == "listado":
            ruta = "/links"
            parametros = {"store": tienda, "limit": 100, "offset": 100 * azar.randrange(paginas)}
        elif tipo == "sku":
            ruta = f"/providers/{proveedor}/suggestions"
            parametros = {"store": tienda, "sku": azar.choice(skus[tienda]), "limit": 20}
        elif tipo == "corridas":
            ruta, parametros = "/runs", {"limit": 20}
        else:
            ruta, parametros = "/links/summary", {"store": tienda}
        consultas.append((segundo + operador / operadores, operador, tipo, ruta, parametros))
    return consultas


# --- Medición y veredicto ----------------------------------------------------------------------


def percentil(valores, p):
    """Rango más cercano: el menor valor que deja al menos `p` de las muestras por debajo."""
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(p * len(ordenados)) - 1)]


def resumir(resultados):
    """Por tipo y en total: consultas, errores y percentiles de latencia en segundos."""
    grupos = {"total": resultados}
    for tipo in PROPORCIONES:
        grupos[tipo] = [r for r in resultados if r["tipo"] == tipo]
    resumen = {}
    for nombre, grupo in grupos.items():
        latencias = [r["latencia"] for r in grupo]
        resumen[nombre] = {
            "consultas": len(grupo),
            "errores": sum(r["estado"] != 200 for r in grupo),
            "p50": percentil(latencias, 0.50),
            "p95": percentil(latencias, 0.95),
            "p99": percentil(latencias, 0.99),
            "maximo": max(latencias, default=None),
        }
    return resumen


def veredicto(resumen, esperadas):
    motivos = []
    total = resumen["total"]
    if total["consultas"] != esperadas:
        motivos.append(f"{total['consultas']} consultas de {esperadas} programadas")
    if total["errores"]:
        motivos.append(f"{total['errores']} consultas sin respuesta exitosa")
    if total["p95"] is None or total["p95"] >= P95_MAXIMO:
        motivos.append("p95 fuera de objetivo")
    return {"cumple": not motivos, "motivos": motivos}


# --- Ejecución ---------------------------------------------------------------------------------


async def consultar(cliente, inicio, consulta, resultados):
    segundo, operador, tipo, ruta, parametros = consulta
    loop = asyncio.get_running_loop()
    await asyncio.sleep(max(0, inicio + segundo - loop.time()))
    try:
        respuesta = await cliente.get(ruta, params=parametros)
        estado = respuesta.status_code
    except httpx.HTTPError as exc:
        estado = type(exc).__name__
    resultados.append(
        {
            "segundo": segundo,
            "operador": operador,
            "tipo": tipo,
            "estado": estado,
            # Desde el instante programado, no desde que salió: incluye cualquier demora propia.
            "latencia": loop.time() - (inicio + segundo),
        }
    )


async def ejecutar(tokens, consultas):
    clientes = [
        httpx.AsyncClient(
            base_url=API,
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
            trust_env=False,
            limits=httpx.Limits(max_connections=20),
        )
        for token in tokens
    ]
    resultados = []
    inicio = asyncio.get_running_loop().time() + 1
    try:
        await asyncio.gather(*(consultar(clientes[c[1]], inicio, c, resultados) for c in consultas))
    finally:
        for cliente in clientes:
            await cliente.aclose()
    return resultados


def credenciales(ruta=Path("data/operadores.txt")):
    # `configurar.py` escribe `usuario: contraseña`, con un espacio después de los dos puntos.
    pares = [
        [parte.strip() for parte in linea.split(":", 1)]
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]
    if len(pares) < OPERADORES:
        raise SystemExit(f"Se necesitan {OPERADORES} cuentas en {ruta}")
    return pares[:OPERADORES]


def preparar(tiendas):
    """Inicia las cinco sesiones y reúne lo necesario para el plan, sin contarlo en la medición."""
    tokens = []
    with httpx.Client(base_url=API, timeout=30, trust_env=False) as anonimo:
        for usuario, clave in credenciales():
            respuesta = anonimo.post("/auth/login", json={"username": usuario, "password": clave})
            respuesta.raise_for_status()
            tokens.append(respuesta.json()["token"])
    with httpx.Client(
        base_url=API, headers={"Authorization": f"Bearer {tokens[0]}"}, timeout=30, trust_env=False
    ) as api:
        total = api.get("/links/summary").json()["total"]
        if total < 2000:
            raise SystemExit(f"Hay {total} vínculos: el ensayo exige al menos 2.000")
        proveedor = next(p["id"] for p in api.get("/providers").json() if p["active"])
        skus, por_tienda = {}, {}
        for tienda in tiendas:
            vinculos, offset = [], 0
            while offset is not None:
                pagina = api.get(
                    "/links", params={"store": tienda, "limit": 100, "offset": offset}
                ).json()
                vinculos += pagina["items"]
                offset = pagina["next_offset"]
            skus[tienda] = [v["sku"] for v in vinculos]
            por_tienda[tienda] = len(vinculos)
    return tokens, proveedor, skus, por_tienda, total


def motor(engine, proveedor):
    """Adelanta una ingesta: la comparación y la publicación corren mientras se consulta."""
    from ivostock import services

    services.schedule_now(engine, proveedor)


def actividad(engine, desde, hasta):
    from ivostock.db import rows

    with engine.begin() as conn:
        corridas = rows(
            conn,
            "SELECT id,status FROM runs WHERE started_at>=:a AND started_at<:b ORDER BY id",
            a=desde,
            b=hasta,
        )
        publicadas = rows(
            conn,
            "SELECT count(*) AS n FROM attempts WHERE status='applied' "
            "AND created_at>=:a AND created_at<:b",
            a=desde,
            b=hasta,
        )[0]["n"]
    return {"corridas": [dict(r) for r in corridas], "publicaciones_aplicadas": publicadas}


# --- Reporte -----------------------------------------------------------------------------------


def segundos_ms(valor):
    return "—" if valor is None else decimal(f"{valor * 1000:.0f}")


def reporte(datos):
    resumen, resultado = datos["resumen"], datos["veredicto"]
    estado = "cumple" if resultado["cumple"] else "no cumple: " + "; ".join(resultado["motivos"])
    lineas = [
        "# Ensayo de consultas (RNF-09)",
        "",
        "Generado por `scripts/ensayo_consultas.py`. Cinco operadores autenticados hacen una "
        "consulta por segundo cada uno durante "
        f"{datos['minutos']} minutos, con carga abierta: cada consulta sale en su segundo "
        "programado y la latencia se mide desde ese instante, en el cliente. Objetivo de "
        "RNF-09: p95 menor a 2 segundos.",
        "",
        f"Ejecutado el {datos['ejecutado'][:16].replace('T', ' ')} UTC sobre "
        f"{datos['vinculos']} vínculos ({datos['fuente']}). **Resultado: {estado}.**",
        "",
        "| Consulta | Cantidad | Errores | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for nombre in (*PROPORCIONES, "total"):
        fila = resumen[nombre]
        etiqueta = "**Total**" if nombre == "total" else DESCRIPCION[nombre]
        lineas.append(
            f"| {etiqueta} | {fila['consultas']} | {fila['errores']} | {segundos_ms(fila['p50'])} "
            f"| {segundos_ms(fila['p95'])} | {segundos_ms(fila['p99'])} "
            f"| {segundos_ms(fila['maximo'])} |"
        )
    motor_activo = datos["motor"]
    corridas = ", ".join(f"#{c['id']} {c['status']}" for c in motor_activo["corridas"]) or "ninguna"
    lineas += [
        "",
        "## Motor durante el ensayo",
        "",
        "Se adelantó una ingesta al empezar y otra a la mitad, para que la comparación y la "
        f"publicación compitan con las consultas. Corridas: {corridas}. Publicaciones aplicadas "
        f"durante la medición: {motor_activo['publicaciones_aplicadas']}.",
        "",
        *seccion_recursos(datos),
        "",
    ]
    return "\n".join(lineas)


# --- Ensayo ------------------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--fuente", choices=["sintetico", "celesa"], required=True)
    ap.add_argument("--tiendas", nargs=2, default=["T1", "T2"])
    ap.add_argument("--minutos", type=int, default=MINUTOS)
    ap.add_argument("--semilla", type=int, default=9)
    ap.add_argument(
        "--reporte-desde", type=Path, help="Regenerar el resumen desde una evidencia JSON"
    )
    args = ap.parse_args(argv)
    destino = Path(f"docs/entregas/ENSAYO-CONSULTAS-{args.fuente.upper()}.md")
    if args.reporte_desde:
        datos = json.loads(args.reporte_desde.read_text(encoding="utf-8"))
        if datos.get("suspensiones"):
            raise SystemExit(invalido(datos, args.reporte_desde))
        destino.write_text(reporte(datos), encoding="utf-8")
        return
    entorno()
    from ivostock.db import database

    engine = database()
    tokens, proveedor, skus, por_tienda, vinculos = preparar(args.tiendas)
    segundos = args.minutos * 60
    consultas = plan(
        args.semilla, OPERADORES, segundos, args.tiendas, skus, proveedor, min(por_tienda.values())
    )
    identificador = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    recursos = Recursos()
    recursos.start()
    desde = datetime.now(UTC)
    try:
        motor(engine, proveedor)

        async def con_motor():
            async def a_la_mitad():
                await asyncio.sleep(segundos / 2)
                await asyncio.to_thread(motor, engine, proveedor)

            mitad = asyncio.create_task(a_la_mitad())
            resultados = await ejecutar(tokens, consultas)
            await mitad
            return resultados

        resultados = asyncio.run(con_motor())
    finally:
        recursos.detener.set()
        recursos.join(timeout=60)
    hasta = datetime.now(UTC) + timedelta(seconds=1)
    resumen = resumir(resultados)
    datos = {
        "ejecutado": datetime.now(UTC).isoformat(),
        "fuente": "inventario real de Celesa" if args.fuente == "celesa" else "feed sintético",
        "minutos": args.minutos,
        "vinculos": vinculos,
        "operadores": OPERADORES,
        "semilla": args.semilla,
        "resumen": resumen,
        "veredicto": veredicto(resumen, len(consultas)),
        "motor": actividad(engine, desde, hasta),
        "maquina": maquina(),
        "recursos": recursos.resumen(),
        "suspensiones": recursos.suspensiones,
        "resultados": resultados,
    }
    evidencia = Path("data/evidencia") / f"ensayo-consultas-{identificador}.json"
    evidencia.parent.mkdir(parents=True, exist_ok=True)
    evidencia.write_text(
        json.dumps(datos, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    if datos["suspensiones"]:
        raise SystemExit(invalido(datos, evidencia))
    destino.write_text(reporte(datos), encoding="utf-8")
    print(reporte(datos))
    sys.exit(0 if datos["veredicto"]["cumple"] else 1)


if __name__ == "__main__":
    main()
