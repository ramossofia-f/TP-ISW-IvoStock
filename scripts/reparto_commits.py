"""Prepara un reparto de entrega sin ejecutar commits, pushes ni cambios de identidad."""

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "691d60eb6e668fa07c996b48f8b8338fb3ed0a48"
MANIFEST = ".reparto-entrega.json"
PEOPLE = {"francisco": "Francisco Ortega", "maria": "María Saráchaga", "sofia": "Sofía Ramos"}
COAUTHORS = {
    "maria": "María Saráchaga <141249907+mariasarachaga@users.noreply.github.com>",
    "sofia": "Sofía Ramos <141259824+ramossofia-f@users.noreply.github.com>",
}
COMMIT_ORDER = (0, 4, 3, 6, 1, 7, 5, 8, 2)
GROUP_COAUTHORS = (
    ("maria", "sofia"),
    ("maria", "sofia"),
    ("maria", "sofia"),
    ("maria", "sofia"),
    ("maria", "sofia"),
    ("maria", "sofia"),
    ("sofia",),
    ("maria", "sofia"),
    ("maria", "sofia"),
)
PURPOSES = [
    "Empaquetado y dependencias bloqueadas; configuración por entorno, PostgreSQL/MinIO, volúmenes y arranque reproducible. Retirar el import de paquete desde src y documentar las decisiones de ejecución.",
    "Contrato HTTP del simulador y catálogo estático; incorporación de tiendas, aprobación y operación de vínculos, CLI y health de la API. Revisar credenciales, paginación y corte seguro con sus responsables.",
    "Guías de ejecución, reglas del repositorio, hitos y reparto de entrega. El exportador prepara un ZIP sin secretos ni Git y sólo copia a cada clon sus archivos asignados.",
    "Contrato fijo SKU;stock, SKU como texto, descartes de duplicados, coeficiente D/Z, snapshots y aceptación/cuarentena transaccional. Conservar eventos durables y reutilizar inventarios idénticos; probar las fallas de P2.",
    "Persistencia SQL, migraciones y aislamiento de la base de pruebas; generador sintético con semilla, parámetros y hashes. Documentar almacenamiento y base compartida.",
    "Requisitos y presentación del producto acordado; contrato de fuentes y límites demostrables. ML queda pendiente; la validación determinista sigue siendo una regla del motor.",
    "Comparación contra confirmado, FIFO con reemplazo, cuota por tienda, leases, reintentos, dead letters y cortes persistidos. Incorporar pruebas de recuperación y confirmaciones atrasadas y retirar el comparador genérico.",
    "CI, logs estructurados sin secretos, health checks, observador de ensayos y verificadores. Comprobar integración y cierres abruptos con servicios reales, sin conservar el test trivial.",
    "Diseño técnico e índice de decisiones, junto con evidencia real de aceptación. Distinguir las mediciones ejecutadas del trabajo pendiente para el MVP y para la entrega remota.",
]
GROUPS = [
    (
        "francisco",
        "chore(p0): preparar paquete y entorno reproducible",
        [
            ".dockerignore",
            ".env.example",
            ".gitignore",
            "Dockerfile",
            "Makefile",
            "docker-compose.yml",
            "docker/minio.Dockerfile",
            "pyproject.toml",
            "uv.lock",
            "scripts/configurar.py",
            "scripts/inicializar.py",
            "src/ivostock/config.py",
            "src/__init__.py",
            "docs/adr/0001-python-fastapi.md",
            "docs/adr/0008-contenedores-ci.md",
            "docs/adr/0004-lenguaje-y-framework.md",
        ],
    ),
    (
        "francisco",
        "feat(p1,p4): implementar marketplace y operación de vínculos",
        [
            "src/ivostock/cli.py",
            "src/ivostock/main.py",
            "src/ivostock/marketplace.py",
            "src/ivostock/services.py",
            "src/ivostock/simulator.py",
            "docs/adr/0006-marketplace-http.md",
            "docs/adr/0001-marketplace-simulado-detras-de-interfaz.md",
        ],
    ),
    (
        "francisco",
        "docs(p5): documentar operación y preparar entrega del equipo",
        [
            "README.md",
            "CLAUDE.md",
            "COMMITS-EQUIPO.md",
            "docs/roadmap/ROADMAP.md",
            "scripts/reparto_commits.py",
        ],
    ),
    (
        "maria",
        "feat(p2): normalizar inventarios y evaluar cuarentena",
        [
            "src/ivostock/feed.py",
            "src/ivostock/ingesta/__init__.py",
            "src/ivostock/ingesta/coeficiente.py",
            "src/ivostock/ingesta/fuente.py",
            "src/ivostock/ingesta/normalizacion.py",
            "src/ivostock/ingesta/servicio.py",
            "src/ivostock/storage.py",
            "scripts/analizar_feed.py",
            "tests/test_feed.py",
            "tests/ingesta/__init__.py",
            "tests/ingesta/test_normalizacion.py",
            "tests/ingesta/test_coeficiente.py",
            "tests/ingesta/test_servicio.py",
        ],
    ),
    (
        "maria",
        "feat(p2): persistir inventarios y generar escenarios reproducibles",
        [
            "src/ivostock/db.py",
            "src/ivostock/schema.sql",
            "alembic.ini",
            "migrations/env.py",
            "migrations/versions/0001_inventory.py",
            "migrations/versions/0002_run_correlation.py",
            "src/ivostock/generador/__init__.py",
            "src/ivostock/generador/feeds.py",
            "tests/generador/__init__.py",
            "tests/generador/test_feeds.py",
            "tests/conftest.py",
            "docs/adr/0002-postgresql-compartido.md",
            "docs/adr/0003-snapshots-s3.md",
            "docs/adr/0005-almacenamiento.md",
            "docs/adr/0007-intercambio-api-motor.md",
        ],
    ),
    (
        "maria",
        "docs(p2): precisar contrato de datos y propuesta del producto",
        [
            "docs/prd/PRD.md",
            "docs/prd/validacion.md",
            "docs/adr/0007-inventarios-deltas.md",
            "docs/adr/0003-componente-ml-deteccion-anomalias.md",
        ],
    ),
    (
        "sofia",
        "feat(p3): comparar vínculos y publicar trabajo durable",
        [
            "src/ivostock/comparison.py",
            "src/ivostock/publisher.py",
            "src/ivostock/quota.py",
            "src/ivostock/worker.py",
            "src/ivostock/failpoints.py",
            "tests/test_pipeline.py",
            "src/ivostock/comparador/__init__.py",
            "src/ivostock/comparador/worker.py",
            "tests/test_comparador.py",
            "docs/adr/0004-cola-postgresql.md",
            "docs/adr/0005-cuota-postgresql.md",
            "docs/adr/0002-propagacion-por-deltas.md",
            "docs/adr/0006-cola-de-tareas-en-postgresql.md",
        ],
    ),
    (
        "sofia",
        "chore(p5): verificar fallas y exponer diagnóstico seguro",
        [
            ".github/workflows/ci.yml",
            "src/ivostock/health.py",
            "src/ivostock/logs.py",
            "tests/test_logs.py",
            "tests/test_dummy.py",
            "scripts/pruebas_locales.py",
            "scripts/verificar_documentacion.py",
            "scripts/verificar_secretos.py",
            "scripts/evaluar_poc.py",
        ],
    ),
    (
        "sofia",
        "docs(p5): describir diseño y registrar evidencia de aceptación",
        [
            "docs/srd/SRD.md",
            "docs/entregas/ENTREGA-2.md",
            "docs/adr/README.md",
        ],
    ),
]


def git(*args, cwd=ROOT):
    return (
        subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.PIPE)
        .decode("utf-8")
        .strip("\n")
    )


def safe_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or any(
        part.casefold().rstrip(" .") in {"", ".git", ".env", ".venv", ".cache", "data", "snapshots"}
        or part == ".."
        for part in relative.parts
    ):
        raise ValueError(f"Ruta excluida del reparto: {relative}")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Ruta fuera del directorio de destino")
    if any(part.casefold() == ".git" for part in resolved.relative_to(root.resolve()).parts):
        raise ValueError("No se modifica metadata de Git")
    return resolved


def inventory():
    changed = set(git("diff", "--name-only", "--no-renames", "-z", BASE).split("\0"))
    changed.update(git("ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    changed.discard("")
    declared = [path for _, _, paths in GROUPS for path in paths]
    if len(declared) != len(set(declared)):
        raise ValueError("Un archivo tiene más de un responsable")
    if changed != set(declared):
        raise ValueError(
            f"Sin asignar: {sorted(changed - set(declared))}; sin cambio: {sorted(set(declared) - changed)}"
        )
    entries = []
    for owner, title, paths in GROUPS:
        for relative in paths:
            path = safe_path(ROOT, relative)
            entries.append(
                {
                    "owner": owner,
                    "commit": title,
                    "path": relative,
                    "action": "write" if path.is_file() else "delete",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                    if path.is_file()
                    else None,
                }
            )
    return {"base": BASE, "entries": entries}


def render():
    manifest = inventory()
    lines = [
        "# Reparto y coautoría de los commits de entrega",
        "",
        "Los cambios se organizan en nueve commits desde este repositorio, con Francisco Ortega como autor Git y las coautorías que corresponden a cada área. El responsable del bloque identifica el reparto de trabajo; no cambia la identidad del autor configurado en Git.",
        "",
        f"Base del trabajo: `{BASE}`. El reparto cubre {len(manifest['entries'])} archivos y eliminaciones, con tres bloques por responsable.",
        "",
        "## Criterio de coautoría",
        "",
        "P0 y P5 son compartidos. P1 corresponde a Francisco con apoyo de Sofía; P4, a Francisco con apoyo de María. P2 corresponde a María con apoyo de Sofía. P3 corresponde a Sofía con apoyo de Francisco. Francisco figura como autor; los aportes de sus compañeras se registran con trailers Co-authored-by y sus emails de GitHub.",
        "",
        "| Orden | Bloque | Responsable | Coautoras |",
        "|---|---|---|---|",
    ]
    for number, index in enumerate(COMMIT_ORDER, 1):
        owner, title, _ = GROUPS[index]
        names = ", ".join(PEOPLE[person] for person in GROUP_COAUTHORS[index])
        lines.append(f"| {number} | `{title}` | {PEOPLE[owner]} | {names} |")
    lines += ["", "## Archivos por commit", ""]
    for number, index in enumerate(COMMIT_ORDER, 1):
        owner, title, paths = GROUPS[index]
        lines += [
            f"### {number}. `{title}`",
            "",
            PURPOSES[index],
            "",
            "| Acción | Archivo |",
            "|---|---|",
        ]
        for relative in paths:
            action = "Actualizar/crear" if (ROOT / relative).is_file() else "Eliminar"
            lines.append(f"| {action} | `{relative}` |")
        lines += ["", "Trailers del mensaje:", "", "```text"]
        lines.extend("Co-authored-by: " + COAUTHORS[person] for person in GROUP_COAUTHORS[index])
        lines += ["```", ""]
    lines += [
        "## Comprobación y publicación",
        "",
        "Verificar el conjunto con los comandos del README y revisar los autores y trailers con `git log --format=full` desde la base indicada. El índice de archivos se comprueba con `python scripts/reparto_commits.py verificar`.",
        "",
        "Los commits son locales. Quedan pendientes el push, la comprobación de CI remoto y el video de entrega. El PR #6 contiene aportes ya adaptados a este árbol; coordinar su cierre después de aceptar la integración para evitar duplicarla. No se modifica su rama ni se hace force-push.",
    ]
    (ROOT / "COMMITS-EQUIPO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def export():
    manifest = inventory()
    files = set(git("ls-files", "-z").split("\0")) | set(
        git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    )
    target = ROOT / "dist/ivostock-equipo.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(files - {""}):
            path = safe_path(ROOT, relative)
            if path.is_file():
                archive.write(path, relative)
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"ZIP preparado: {target.relative_to(ROOT)}")


def prepare(owner, destination):
    destination = destination.resolve()
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    if (
        manifest["base"] != BASE
        or Path(git("rev-parse", "--show-toplevel", cwd=destination)).resolve() != destination
    ):
        raise ValueError("Base o raíz de repositorio incorrecta")
    if git("branch", "--show-current", cwd=destination) != f"entrega-2/{owner}":
        raise ValueError("Crear primero la rama personal indicada en la guía")
    if git("rev-parse", "HEAD", cwd=destination) != manifest["base"] or git(
        "status", "--porcelain", cwd=destination
    ):
        raise ValueError("El destino debe ser un clon limpio en la base común")
    entries = [entry for entry in manifest["entries"] if entry["owner"] == owner]
    expected = {
        (title, relative)
        for person, title, paths in GROUPS
        if person == owner
        for relative in paths
    }
    if (
        len(entries) != len(expected)
        or {(entry["commit"], entry["path"]) for entry in entries} != expected
    ):
        raise ValueError("El manifiesto no coincide con los archivos asignados")
    for entry in entries:
        if entry["action"] == "write":
            source = safe_path(ROOT, entry["path"])
            if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"Hash distinto al del paquete: {entry['path']}")
        safe_path(destination, entry["path"])
    for entry in entries:
        target = safe_path(destination, entry["path"])
        if entry["action"] == "delete":
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_path(ROOT, entry["path"]), target)
    print(
        f"Bloque de {PEOPLE[owner]} preparado: {len(entries)} archivos. Revisar y commitear según COMMITS-EQUIPO.md."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("verificar", "documentar", "exportar"):
        sub.add_parser(command)
    command = sub.add_parser("preparar")
    command.add_argument("persona", choices=PEOPLE)
    command.add_argument("--destino", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preparar":
        prepare(args.persona, args.destino)
    elif args.command == "documentar":
        render()
    elif args.command == "exportar":
        export()
    else:
        manifest = inventory()
        print(
            f"Reparto completo: {len(manifest['entries'])} archivos, nueve commits, tres integrantes."
        )


if __name__ == "__main__":
    main()
