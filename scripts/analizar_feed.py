#!/usr/bin/env python3
"""
Analiza snapshots crudos de un feed de stock en formato `SKU;stock`.

Es la herramienta con la que se midio el feed real de Celesa para la seccion 12
del PRD. Sirve para dos cosas:

1. Caracterizar UNA corrida: volumen, encoding, calidad de parseo (RF-21),
   duplicados, distribucion de stock y proyeccion de almacenamiento.

2. Comparar DOS corridas consecutivas del mismo proveedor y calcular las senales
   del coeficiente de sospecha de CU-07: `D` (SKU que desaparecieron), `Z` (ceros
   nuevos en masa) y el coeficiente `p` resultante, ademas de la fraccion de
   deltas que la corrida generaria (S-07).

Los snapshots son datos de un tercero y NO se versionan: se pasan por parametro.

Uso:
    python scripts/analizar_feed.py <snapshot>
    python scripts/analizar_feed.py <snapshot_previo> <snapshot_nuevo>
    python scripts/analizar_feed.py <snapshot> --sep ';' --sku 0 --stock 1

Formato esperado: una linea por SKU, sin encabezado, campos separados por `;`,
SKU en la posicion 0 y stock en la posicion 1. Los tres valores son
configurables para otros proveedores.
"""

import argparse
import collections
import gzip
import os
import statistics
import sys

TOLERANCIA_D = 0.10   # CU-07: valor que satura la senal D
TOLERANCIA_Z = 0.25   # CU-07: valor que satura la senal Z
UMBRAL_CUARENTENA = 0.5
UMBRAL_ALERTA_PARSEO = 0.10   # RF-44


def leer(ruta):
    """Devuelve (texto, bytes_crudos, encoding). Acepta .gz."""
    abrir = gzip.open if ruta.endswith(".gz") else open
    with abrir(ruta, "rb") as fh:
        crudo = fh.read()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return crudo.decode(encoding), crudo, encoding
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"No se pudo decodificar {ruta} con utf-8, cp1252 ni latin-1")


def parsear(texto, sep, pos_sku, pos_stock):
    """Aplica las reglas de RF-21 y devuelve el estado vigente mas las metricas."""
    vigente = {}
    m = collections.Counter()
    apariciones = collections.Counter()
    longitudes = collections.Counter()
    ejemplos = collections.defaultdict(list)

    for linea in texto.splitlines():
        if not linea.strip():
            m["vacias"] += 1
            continue
        campos = linea.split(sep)
        if len(campos) <= max(pos_sku, pos_stock):
            m["mal_formadas"] += 1
            _guardar(ejemplos, "mal_formadas", linea)
            continue
        sku = campos[pos_sku].strip()
        stock = campos[pos_stock].strip()
        apariciones[sku] += 1
        longitudes[len(sku)] += 1
        if not sku.isdigit():
            m["sku_alfanumerico"] += 1
            _guardar(ejemplos, "sku_alfanumerico", linea)

        # RF-21: en blanco NO es error de parseo, se interpreta como sin stock.
        if stock == "":
            m["blanco"] += 1
            vigente[sku] = 0
            continue
        try:
            valor = int(stock)
        except ValueError:
            m["stock_no_numerico"] += 1
            _guardar(ejemplos, "stock_no_numerico", linea)
            continue
        if valor < 0:
            m["stock_negativo"] += 1
            _guardar(ejemplos, "stock_negativo", linea)
            continue
        vigente[sku] = valor       # duplicado: vale la ultima ocurrencia (RF-21)

    m["duplicados"] = sum(1 for c in apariciones.values() if c > 1)
    return vigente, m, apariciones, longitudes, ejemplos


def _guardar(ejemplos, clave, linea, tope=5):
    if len(ejemplos[clave]) < tope:
        ejemplos[clave].append(linea)


def describir(ruta, sep, pos_sku, pos_stock, salida):
    texto, crudo, encoding = leer(ruta)
    tam = len(crudo)
    vigente, m, apariciones, longitudes, ejemplos = parsear(texto, sep, pos_sku, pos_stock)

    lineas = texto.splitlines()
    filas = len(lineas) - m["vacias"]
    err = m["stock_no_numerico"] + m["stock_negativo"] + m["mal_formadas"]
    valores = list(vigente.values())
    positivos = [v for v in valores if v > 0]
    ceros = len(valores) - len(positivos)

    p = salida.append
    p("=" * 70)
    p(f"SNAPSHOT: {os.path.basename(ruta)}")
    p("=" * 70)
    p("")
    p("VOLUMEN Y FORMATO")
    p(f"  Tamano                  {tam:,} bytes ({tam / 1024 / 1024:.2f} MB)")
    p(f"  Encoding                {encoding}" + ("  (con BOM)" if crudo[:3] == b"\xef\xbb\xbf" else ""))
    p(f"  Fin de linea            {'CRLF' if crudo.count(b'CRLF'[:2]) else 'LF'}")
    p(f"  Filas con dato          {filas:,}")
    p(f"  SKU distintos           {len(apariciones):,}")
    p(f"  SKU en estado vigente   {len(vigente):,}")
    p(f"  Bytes por linea         {tam / max(filas, 1):.1f}")
    p("")
    p("CALIDAD DE PARSEO  (RF-21 / RF-44)")
    p(f"  Stock no numerico       {m['stock_no_numerico']:,}")
    p(f"  Stock negativo          {m['stock_negativo']:,}")
    p(f"  Filas mal formadas      {m['mal_formadas']:,}")
    tasa = err / filas if filas else 0
    estado = "ALERTA (RF-44)" if tasa > UMBRAL_ALERTA_PARSEO else "ok"
    p(f"  TOTAL error de parseo   {err:,}  ({tasa * 100:.4f} %)  umbral {UMBRAL_ALERTA_PARSEO:.0%} -> {estado}")
    p("")
    p(f"  Stock en blanco (= 0)   {m['blanco']:,}   no es error de parseo")
    p(f"  SKU duplicados          {m['duplicados']:,}   vale la ultima ocurrencia")
    p(f"  SKU alfanumericos       {m['sku_alfanumerico']:,}   validos: el SKU es cadena, no numero")
    p(f"  Longitudes de SKU       {dict(longitudes.most_common(5))}")
    for clave, muestras in sorted(ejemplos.items()):
        if muestras:
            p(f"  Ejemplos {clave:<15} {muestras}")
    p("")
    p("DISTRIBUCION DE STOCK")
    p(f"  SKU con stock 0         {ceros:,}  ({ceros / max(len(valores), 1) * 100:.2f} %)")
    p(f"  SKU con stock > 0       {len(positivos):,}")
    if positivos:
        orden = sorted(positivos)
        p(f"  Unidades totales        {sum(valores):,}")
        p(f"  min / mediana / max     {orden[0]} / {statistics.median(orden):.0f} / {orden[-1]:,}")
        for pct in (50, 90, 99):
            p(f"  percentil {pct:<2} (> 0)      {orden[min(int(len(orden) * pct / 100), len(orden) - 1)]}")
    p("")
    p("PROYECCION DE ALMACENAMIENTO  (48 corridas/dia, cada 30 min)")
    comprimido = len(gzip.compress(crudo))
    p(f"  Crudo por dia           {tam * 48 / 1024 / 1024:.0f} MB      por mes {tam * 48 * 30 / 1024 ** 3:.2f} GB")
    p(f"  Comprimido (gzip)       {comprimido / tam * 100:.1f} % del original")
    p(f"  Comprimido por dia      {comprimido * 48 / 1024 / 1024:.0f} MB      por mes {comprimido * 48 * 30 / 1024 ** 3:.2f} GB")
    p("")
    p("COSTO CONTRA LA CUOTA DE UNA TIENDA  (60 req/min = 3.600/hora, S-08)")
    p(f"  Escribir los {len(vigente):,} SKU de una vez: {len(vigente) / 3600:.1f} horas")
    p(f"  -> por eso se propaga por deltas y no por reescritura (ADR-0002)")
    p("")
    return vigente


def comparar(previo, nuevo, salida):
    """Senales del coeficiente de sospecha de CU-07 entre dos corridas."""
    p = salida.append
    base = len(previo)
    con_stock = sum(1 for v in previo.values() if v > 0)

    ausentes = [s for s in previo if s not in nuevo]
    nuevos = [s for s in nuevo if s not in previo]
    ceros_nuevos = [s for s, v in previo.items() if v > 0 and nuevo.get(s) == 0]
    deltas = [s for s, v in nuevo.items() if previo.get(s) != v]

    D = len(ausentes) / base if base else 0.0
    Z = len(ceros_nuevos) / con_stock if con_stock else 0.0
    d = min(1.0, D / TOLERANCIA_D)
    z = min(1.0, Z / TOLERANCIA_Z)
    coef = 1 - (1 - d) * (1 - z)

    p("=" * 70)
    p("COMPARACION ENTRE CORRIDAS  (CU-07)")
    p("=" * 70)
    p("")
    p(f"  SKU en el snapshot previo   {base:,}")
    p(f"  SKU en la corrida nueva     {len(nuevo):,}")
    p(f"  SKU que desaparecieron      {len(ausentes):,}")
    p(f"  SKU nuevos                  {len(nuevos):,}")
    p(f"  SKU que pasaron a 0         {len(ceros_nuevos):,}")
    p("")
    p(f"  D = {D:.6f}   -> d = min(1, D/{TOLERANCIA_D}) = {d:.4f}")
    p(f"  Z = {Z:.6f}   -> z = min(1, Z/{TOLERANCIA_Z}) = {z:.4f}")
    p(f"  p = 1 - (1-d)(1-z) = {coef:.4f}")
    veredicto = "CUARENTENA" if coef > UMBRAL_CUARENTENA else "se acepta"
    p(f"  umbral {UMBRAL_CUARENTENA} -> {veredicto}")
    p("")
    p(f"  Deltas a propagar           {len(deltas):,}  ({len(deltas) / max(len(nuevo), 1) * 100:.2f} % del catalogo)")
    p(f"  -> S-07 se sostiene si ese porcentaje se mantiene chico")
    p("")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshots", nargs="+", help="uno (caracterizar) o dos (comparar: previo y nuevo)")
    ap.add_argument("--sep", default=";", help="separador de campos (default: ';')")
    ap.add_argument("--sku", type=int, default=0, help="posicion del campo SKU (default: 0)")
    ap.add_argument("--stock", type=int, default=1, help="posicion del campo stock (default: 1)")
    ap.add_argument("-o", "--out", help="ademas de imprimir, escribe el reporte en este archivo")
    args = ap.parse_args()

    if len(args.snapshots) > 2:
        ap.error("se aceptan como maximo dos snapshots")
    for ruta in args.snapshots:
        if not os.path.exists(ruta):
            ap.error(f"no existe: {ruta}")

    salida = []
    estados = [describir(r, args.sep, args.sku, args.stock, salida) for r in args.snapshots]
    if len(estados) == 2:
        comparar(estados[0], estados[1], salida)
    else:
        salida.append("Para calcular D, Z y el coeficiente de CU-07 hacen falta dos snapshots.")
        salida.append("")

    reporte = "\n".join(salida)
    print(reporte)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(reporte)
        print(f"[reporte escrito en {args.out}]", file=sys.stderr)


if __name__ == "__main__":
    main()
