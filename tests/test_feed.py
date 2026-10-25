import hashlib

import pytest

from ivostock.feed import changes, parse, prepare, suspicion


def test_fixed_contract_and_traced_rows():
    feed = parse(b"SKU;stock\nABC-X;4\nABC-X;8\nB;\nC;-1\nD;no\nE;2;3\nABC-X;invalid\n")
    assert feed.stock == {"ABC-X": 8, "B": 0}
    assert feed.duplicates == 1
    assert [d["line"] for d in feed.discarded] == [2, 5, 6, 7, 8]


@pytest.mark.parametrize("raw", [b"A;2\n", b"sku;stock\n", b"SKU,stock\n", b""])
def test_header_required(raw):
    with pytest.raises(ValueError):
        parse(raw)


def test_missing_sku_is_a_zero_delta():
    assert changes({"A": 3, "B": 5, "C": 0}, {"A": 3}) == {"B": 0}


def test_quantity_out_of_range_is_a_row_discard():
    feed = parse(b"SKU;stock\nA;" + b"9" * 5000 + b"\nB;1\n")
    assert feed.stock == {"B": 1}
    assert feed.discarded == [{"line": 2, "reason": "quantity_range"}]


def test_guard_keeps_missing_and_explicit_zero_separate():
    previous = {str(n): 1 for n in range(100)}
    current = {**previous}
    del current["0"]
    current["1"] = 0
    score = suspicion(previous, current)
    assert score["D"] == 0.01
    assert score["Z"] == 0.01
    assert score["p"] == pytest.approx(0.136)
    assert suspicion(previous, {})["p"] == 1


def test_preparation_changes_only_the_header(tmp_path):
    original = b"ISBN-X;12\r\nB;3\r\n"
    source = tmp_path / "original"
    source.write_bytes(original)
    manifest = prepare(source, tmp_path / "http", "fixture sintética", "2026-10-25")
    derived = (tmp_path / "http" / manifest["file"]).read_bytes()
    assert derived == b"SKU;stock\n" + original
    assert source.read_bytes() == original
    assert hashlib.sha256(original).hexdigest() == manifest["original_sha256"]
