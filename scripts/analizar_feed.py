"""Caracteriza uno o dos snapshots del contrato SKU;stock (ADR-0007)."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from ivostock.feed import changes, parse, suspicion


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("snapshots", nargs="+", type=Path)
    args = ap.parse_args()
    if not 1 <= len(args.snapshots) <= 2:
        ap.error("Indicar uno o dos snapshots con encabezado")
    parsed = []
    reports = []
    for path in args.snapshots:
        raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        feed = parse(raw)
        parsed.append(feed.stock)
        reports.append(
            {
                "file": path.name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "rows": feed.lines,
                "sku": len(feed.stock),
                "duplicates": feed.duplicates,
                "parse_error_rate": feed.error_rate,
                "discards": feed.discarded,
                "zeros": sum(q == 0 for q in feed.stock.values()),
            }
        )
    output = {"snapshots": reports}
    if len(parsed) == 2:
        output["comparison"] = {**suspicion(*parsed), "deltas": len(changes(*parsed))}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
