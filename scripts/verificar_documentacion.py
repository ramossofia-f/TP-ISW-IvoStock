"""Comprueba enlaces locales, referencias y numeración del alcance vigente."""

import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
documents = [
    root / "README.md",
    root / "CLAUDE.md",
    root / "COMMITS-EQUIPO.md",
    *sorted((root / "docs").rglob("*.md")),
]
documents = [p for p in documents if "consignas" not in p.parts]
prd = (root / "docs/prd/PRD.md").read_text(encoding="utf-8")
known = set()
for prefix in ("RF", "RNF", "CU"):
    ids = re.findall(rf"^\| ({prefix}-\d+) \|", prd, re.M)
    expected = [f"{prefix}-{n:02}" for n in range(1, len(ids) + 1)]
    assert ids == expected, (prefix, ids)
    known.update(ids)
adrs = sorted((root / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
assert [p.name[:4] for p in adrs] == [f"{n:04}" for n in range(1, 9)]
for path in documents:
    content = path.read_text(encoding="utf-8")
    for reference in re.findall(r"\b(?:RNF|RF|CU)-\d+\b", content):
        assert reference in known, (path, reference)
    for target in re.findall(r"\]\(([^)]+)\)", content):
        if "://" in target or target.startswith("#"):
            continue
        assert (path.parent / target.split("#")[0]).exists(), (path, target)
print(
    f"Documentación coherente: {len(documents)} documentos, {len(known)} requisitos/casos y 8 ADRs"
)
