"""Detecta secretos locales filtrados y datos privados en archivos del producto."""

import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
excluded = {
    ".git",
    ".venv",
    ".cache",
    ".claude",
    "data",
    "snapshots",
    "consignas",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}
secrets = []
env = root / ".env"
if env.exists():
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" in line and any(
            word in line.split("=", 1)[0] for word in ("PASSWORD", "SECRET", "TOKEN", "ACCESS_KEY")
        ):
            value = line.split("=", 1)[1]
            if len(value) >= 16:
                secrets.append(value)
for path in root.rglob("*"):
    if (
        not path.is_file()
        or excluded.intersection(path.relative_to(root).parts)
        or path.name.startswith(".env")
    ):
        continue
    if path.suffix.lower() in (".csv", ".tsv", ".gz", ".docx"):
        raise SystemExit(f"Dato o documento binario inesperado: {path.relative_to(root)}")
    content = path.read_text(encoding="utf-8")
    assert not any(value in content for value in secrets), (
        f"Secreto local en {path.relative_to(root)}"
    )
    assert not re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", content), (
        f"Clave privada en {path.relative_to(root)}"
    )
print("Comprobación de secretos y datos privados: correcta")
