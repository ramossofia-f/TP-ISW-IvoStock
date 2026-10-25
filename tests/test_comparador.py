from ivostock.comparador.worker import comparar_stock


def test_comparar_stock_sin_cambios():
    actual = [{"id": 1, "qty": 10, "precio": 100}]
    nuevo = [{"id": 1, "qty": 10, "precio": 100}]
    diff = comparar_stock(actual, nuevo)
    assert len(diff) == 0

def test_comparar_stock_completo():
    actual = [
        {"id": 1, "qty": 10, "precio": 100},  # Sin cambios
        {"id": 2, "qty": 5, "precio": 50},   # Será modificado
        {"id": 4, "qty": 2, "precio": 20}    # Será eliminado
    ]
    nuevo = [
        {"id": 1, "qty": 10, "precio": 100},  # Sin cambios
        {"id": 2, "qty": 8, "precio": 60},   # Modificado (cambió qty y precio)
        {"id": 3, "qty": 20, "precio": 200}  # Nuevo
    ]
    
    diff = comparar_stock(actual, nuevo)
    
    assert len(diff) == 3
    
    tipos = {d["id"]: d["tipo"] for d in diff}
    assert tipos[2] == "MODIFICADO"
    assert tipos[3] == "NUEVO"
    assert tipos[4] == "ELIMINADO"
