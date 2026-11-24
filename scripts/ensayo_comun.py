"""Piezas compartidas por los ensayos de RNF-02/RNF-15 (dos tiendas) y RNF-09 (consultas).

Entorno del host, CLI dentro de Docker, muestreo de recursos con detección de suspensiones y la
sección de recursos de los reportes.
"""

import json
import os
import platform
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MUESTRAS_MINIMAS = 3
# Un equipo suspendido detiene a Docker y a los servicios: el ensayo deja de ser válido.
SUSPENSION_MINIMA = 60


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


def suspension(antes, despues):
    """Segundos suspendidos entre dos lecturas `(reloj de pared, reloj monotónico)`.

    El reloj monotónico no avanza mientras el equipo duerme (macOS y Linux); el de pared sí.
    """
    perdidos = (despues[0] - antes[0]) - (despues[1] - antes[1])
    return perdidos if perdidos >= SUSPENSION_MINIMA else 0


class Recursos(threading.Thread):
    """Muestrea `docker stats` del proyecto mientras dura el ensayo (RNF-15).

    También detecta suspensiones del equipo, que invalidan las mediciones de tiempo.
    """

    def __init__(self, cada=30):
        super().__init__(daemon=True)
        self.cada, self.muestras, self.detener = cada, {}, threading.Event()
        self.suspensiones = []
        self.proyecto = os.environ.get("COMPOSE_PROJECT_NAME") or Path.cwd().name

    def run(self):
        anterior = (time.time(), time.monotonic())
        while not self.detener.is_set():
            actual = (time.time(), time.monotonic())
            if perdidos := suspension(anterior, actual):
                desde = datetime.fromtimestamp(anterior[0], UTC).isoformat()
                self.suspensiones.append({"desde": desde, "segundos": round(perdidos)})
            anterior = actual
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


def decimal(valor):
    return str(valor).replace(".", ",")


def invalido(datos, evidencia):
    minutos_dormido = sum(s["segundos"] for s in datos["suspensiones"]) / 60
    return (
        f"Ensayo inválido: el equipo estuvo suspendido {minutos_dormido:.0f} minutos "
        f"({len(datos['suspensiones'])} veces) y las duraciones incluyen ese tiempo. "
        f"No se escribe el reporte; detalle en {evidencia}. Repetir con el equipo enchufado y "
        "sin suspensión, por ejemplo con `caffeinate -i` en macOS."
    )


def seccion_recursos(datos):
    return [
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
    ]
