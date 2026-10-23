def comparar_stock(stock_actual: list, stock_nuevo: list) -> list:
    """
    Compara el stock actual con el nuevo stock recibido.
    Detecta elementos nuevos, modificados y eliminados.
    """
    actual_dict = {item.get("id"): item for item in stock_actual}
    nuevo_dict = {item.get("id"): item for item in stock_nuevo}
    
    diferencias = []
    
    # Revisar nuevos y modificados
    for item_id, nuevo_item in nuevo_dict.items():
        if item_id not in actual_dict:
            diferencias.append({"id": item_id, "estado": "nuevo", "item": nuevo_item})
        else:
            actual_item = actual_dict[item_id]
            if actual_item != nuevo_item:
                diferencias.append({
                    "id": item_id, 
                    "estado": "modificado", 
                    "anterior": actual_item, 
                    "nuevo": nuevo_item
                })
                
    # Revisar eliminados
    for item_id, actual_item in actual_dict.items():
        if item_id not in nuevo_dict:
            diferencias.append({"id": item_id, "estado": "eliminado", "item": actual_item})
            
    return diferencias
