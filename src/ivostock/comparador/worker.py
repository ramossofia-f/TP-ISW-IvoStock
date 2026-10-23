from typing import List, Dict, Any

def comparar_stock(stock_actual: List[Dict[str, Any]], stock_nuevo: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compara el stock actual con el nuevo stock recibido implementando 
    el modelo de propagación por deltas.
    Detecta elementos NUEVOS, MODIFICADOS (con detalle de cambios) y ELIMINADOS.
    """
    actual_dict = {item.get("id"): item for item in stock_actual}
    nuevo_dict = {item.get("id"): item for item in stock_nuevo}
    
    deltas = []
    
    # 1. Revisar ítems nuevos y modificados
    for item_id, nuevo_item in nuevo_dict.items():
        if item_id not in actual_dict:
            deltas.append({
                "id": item_id,
                "tipo": "NUEVO",
                "item_nuevo": nuevo_item
            })
        else:
            actual_item = actual_dict[item_id]
            cambios = {}
            for key in ["qty", "precio", "stock", "cantidad"]:
                if key in nuevo_item and key in actual_item and nuevo_item[key] != actual_item[key]:
                    cambios[key] = {
                        "anterior": actual_item[key], 
                        "nuevo": nuevo_item[key]
                    }
            
            if cambios or actual_item != nuevo_item:
                deltas.append({
                    "id": item_id,
                    "tipo": "MODIFICADO",
                    "cambios": cambios,
                    "item_anterior": actual_item,
                    "item_nuevo": nuevo_item
                })
                
    # 2. Revisar ítems eliminados
    for item_id, actual_item in actual_dict.items():
        if item_id not in nuevo_dict:
            deltas.append({
                "id": item_id,
                "tipo": "ELIMINADO",
                "item_anterior": actual_item
            })
            
    return deltas
