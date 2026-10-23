from src.ivostock.comparador.worker import comparar_stock

def test_comparar_stock_completo():
    actual = [
        {"id": 1, "qty": 10, "precio": 100},
        {"id": 2, "qty": 5, "precio": 50}
    ]
    nuevo = [
        {"id": 1, "qty": 10, "precio": 100},  # Sin cambios
        {"id": 2, "qty": 8, "precio": 50},   # Modificado (cambió qty)
        {"id": 3, "qty": 20, "precio": 200}  # Nuevo
    ]
    
    diff = comparar_stock(actual, nuevo)
    
    # Debe detectar exactamente 2 diferencias (el id 2 modificado y el id 3 nuevo)
    assert len(diff) == 2
    
    estados = {d["id"]: d["estado"] for d in diff}
    assert estados[2] == "modificado"
    assert estados[3] == "nuevo"
