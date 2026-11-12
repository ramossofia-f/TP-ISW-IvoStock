# ADR-0015: Detector de feeds anómalos como señal adicional de la guarda

Estado: propuesto. Fecha: 12/11/2026.

## Contexto y alternativas

RF-27 pide un componente de ML con entrenamiento reproducible, inferencia y monitoreo, y deja el problema sin definir. El riesgo central del producto es aceptar un inventario defectuoso: cada SKU ausente pasa a cero (RF-12) y se publica en todas las tiendas vinculadas. La guarda de RF-13 decide con dos señales y tolerancias fijas (`D` sobre 0,10 y `Z` sobre 0,25, cuarentena si `p > 0,5`). Tiene dos puntos ciegos conocidos:

- Un truncamiento menor al 5 % da `p ≤ 0,5` y se acepta. Con los 255.129 SKU de Celesa, un 2 % son unos 5.000 SKU llevados a cero por error.
- Un agotamiento legítimo y masivo, por ejemplo de temporada, supera la tolerancia de `Z` y frena la corrida aunque el feed sea correcto.

Los datos disponibles son un snapshot real de Celesa, fuera de Git, y el generador con semilla del [ADR-0007](0007-inventarios-deltas.md), que produce truncamientos, ceros, filas corruptas y deriva con etiquetas conocidas. No hay historial real de corridas.

Para el problema se compararon tres alternativas:

- **Predicción de agotamiento por SKU.** Serviría para priorizar la cola, pero exige series de stock por SKU. Con un solo snapshot real, el historial y la evaluación serían inventados, y un error del modelo sólo reordena trabajo sin evitar daño.
- **Vinculación SKU ↔ publicación por similitud.** Ampliaría las sugerencias de RF-06, pero los atributos del catálogo son sintéticos ([README](../../README.md)): no hay una verdad contra la cual medir precisión.
- **Detección de corridas defectuosas.** Ataca el riesgo central. El generador entrega etiquetas reproducibles y la guarda actual sirve de línea de base medible. A cambio, las etiquetas son sintéticas y el modelo puede aprender artefactos del generador; se mitiga evaluando también sobre escenarios derivados del snapshot real.

Para el modelo:

- **Ajustar las tolerancias de la guarda.** No agrega señales: mover el umbral de `D` para cubrir truncamientos chicos aumenta las falsas cuarentenas, y no cumple RF-27.
- **Gradient boosting o isolation forest.** Capturan interacciones, pero son menos interpretables, su artefacto es un binario (`pickle`) que ejecuta código al cargarse, y con pocas variables no se espera una mejora que lo justifique.
- **Regresión logística sobre variables de la corrida.** Es interpretable: cada coeficiente dice qué señal pesa. Se entrena con scikit-learn y se exporta como JSON (coeficientes, medias y escalas), así la inferencia es aritmética en Python puro, sin scikit-learn en la imagen y sin deserializar código.

Para el rol frente a la guarda:

- **Reemplazarla.** Contradice RF-13 («no existe aprobación que omita la guarda») y haría depender la seguridad de un modelo entrenado con datos sintéticos.
- **Sólo informativo.** Es lo más seguro, pero no corrige ninguno de los dos puntos ciegos.
- **Señal adicional y monótona.** La guarda decide igual que hoy; el modelo sólo puede agregar cuarentenas que la guarda dejó pasar, nunca liberar una que frenó.

## Decisión

Se implementa un detector de corridas defectuosas con regresión logística, que actúa como señal adicional y monótona de la guarda.

- **Variables** de cada corrida contra el último inventario aceptado, calculadas en `ivostock.ml` por una única función compartida por entrenamiento e inferencia: `D`, `Z`, tasa de errores de parseo, variación relativa de la cantidad de SKU, concentración de los ausentes al final del archivo anterior (un truncamiento corta la cola), proporción de cantidades que cambian y distancia de Kolmogorov-Smirnov entre las distribuciones de cantidades. La concentración necesita el orden del archivo anterior, así que la ingesta toma el previo del snapshot de la última corrida aceptada y no de la tabla `stock`.
- **Datos.** `ivostock.ml.datos` genera el conjunto de entrenamiento con el generador y semilla fija: corridas normales (deriva y agotamientos dispersos, incluidos agotamientos masivos legítimos) y defectuosas (truncamiento desde 0,5 %, ceros masivos, filas corruptas). Se agrega al generador un parámetro de bajas dispersas para que una desaparición legítima no sea sinónimo de defecto. Los parámetros y la semilla del conjunto se versionan; los archivos generados no.
- **Entrenamiento y evaluación.** `scripts/ml_entrenar.py` entrena con scikit-learn en un grupo de dependencias `ml`, separado del runtime, y escribe `src/ivostock/ml/modelo.json` con versión, semilla, hash del conjunto y métricas. Se evalúa por escenario contra la guarda: recall de defectuosas, tasa de falsas cuarentenas y, en particular, truncamientos menores al 5 %. El umbral se fija en un conjunto de validación disjunto para que el modelo agregue a lo sumo un 1 % de falsas cuarentenas entre las corridas normales que la guarda acepta. Con `--base` se evalúa además sobre escenarios aplicados al inventario real, que no entra al entrenamiento.
- **Inferencia.** La ingesta calcula el puntaje del modelo después de la guarda y lo guarda en `runs.metrics` (`ml_score`, `ml_version`). Si la guarda acepta y el puntaje supera el umbral, la corrida va a cuarentena con motivo `ml`; el reemplazo por CLI (`replay`) la reproduce igual. Si el modelo no carga, la ingesta sigue sólo con la guarda y lo registra.
- **Monitoreo.** Un comando de backend (`ivostock ml-report`) resume la distribución de puntajes, las cuarentenas por motivo (`guarda` o `ml`) y la deriva de cada variable respecto del conjunto de entrenamiento (PSI), y el tablero de corridas muestra el motivo.

## Consecuencias

El modelo sólo puede hacer más conservadora la aceptación: en el peor caso agrega cuarentenas, que ya tienen tratamiento (reemplazo manual y proveedor degradado), y nunca acepta lo que hoy se frena. RNF-03 no cambia. Las métricas valen para escenarios sintéticos; no acreditan el comportamiento con proveedores reales, y así se declaran. Cambiar el generador o las variables exige reentrenar y versionar un `modelo.json` nuevo. Se agregan scikit-learn y numpy sólo al grupo `ml`; la imagen de los workers no cambia de dependencias. El segundo punto ciego (agotamiento legítimo que la guarda frena) queda medido pero no resuelto, porque el rol monótono no permite liberar cuarentenas. La variable de concentración supone que el proveedor conserva el orden de su archivo entre corridas; si lo reordena, el truncamiento leve deja de distinguirse, y la deriva de esa variable es una de las que vigila el monitoreo.

## Comprobación

Pruebas unitarias: las variables coinciden entre entrenamiento e inferencia; el mismo conjunto y la misma semilla producen el mismo `modelo.json`; la inferencia en Python puro coincide con scikit-learn; el modelo nunca libera una corrida que la guarda frena. Prueba de integración: un truncamiento del 2 % que la guarda acepta queda en cuarentena con motivo `ml` y no genera tareas. El reporte de evaluación por escenario se versiona en `docs/entregas/`.
