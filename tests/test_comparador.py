from src.ivostock.comparador.worker import comparar_stock

def test_comparar_stock():
    actual = [{"id": 1, "qty": 10}]
    nuevo = [{"id": 1, "qty": 10}, {"id": 2, "qty": 5}]
    diff = comparar_stock(actual, nuevo)
    assert len(diff) == 1
    assert diff[0]["item"]["id"] == 2
