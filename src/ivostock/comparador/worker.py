def comparar_stock(stock_actual, stock_nuevo):
    diferencias = []
    for item in stock_nuevo:
        if item not in stock_actual:
            diferencias.append({"item": item, "estado": "nuevo"})
    return diferencias
