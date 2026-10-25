"""Normalización del contrato fijo con descarte de la ocurrencia sustituida."""

from dataclasses import dataclass


@dataclass
class Feed:
    stock: dict[str, int]
    discarded: list[dict]
    duplicates: int
    lines: int

    @property
    def error_rate(self):
        errors = sum(d["reason"] != "duplicate" for d in self.discarded)
        return errors / self.lines if self.lines else 0


def normalizar(raw: bytes) -> Feed:
    lines = raw.decode("utf-8").splitlines()
    if not lines or lines[0] != "SKU;stock":
        raise ValueError("Se requiere primera fila SKU;stock en UTF-8")
    stock, discarded, last_valid_line = {}, [], {}
    duplicates = 0
    for number, line in enumerate(lines[1:], 2):
        fields = line.split(";")
        if len(fields) != 2 or not fields[0].strip():
            discarded.append({"line": number, "reason": "columns_or_sku"})
            continue
        sku, value = (field.strip() for field in fields)
        if value and (not value.isascii() or not value.isdecimal()):
            discarded.append({"line": number, "reason": "quantity"})
            continue
        significant = value.lstrip("0") or "0"
        if len(significant) > 10 or int(significant) > 2147483647:
            discarded.append({"line": number, "reason": "quantity_range"})
            continue
        if sku in last_valid_line:
            duplicates += 1
            discarded.append({"line": last_valid_line[sku], "reason": "duplicate"})
        last_valid_line[sku] = number
        stock[sku] = int(significant)
    return Feed(
        stock, sorted(discarded, key=lambda discard: discard["line"]), duplicates, len(lines) - 1
    )
