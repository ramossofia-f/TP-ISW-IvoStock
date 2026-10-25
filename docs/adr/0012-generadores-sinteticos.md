# ADR-0012: Generadores sintéticos reproducibles con semilla

## Contexto y problema

El feed real de Celesa permite medir el caso habitual, pero no produce a demanda feeds truncados, columnas vacías, separadores distintos ni ceros en masa. El lado de MercadoLibre es simulado (ADR-0001) y su catálogo tiene que generarse. El PRD trata los dos generadores como requisitos del sistema (RF-36, RF-37), y la consigna evalúa el mecanismo de generación cuando los datos son sintéticos. Hay que decidir cómo se generan esos datos.

## Factores de decisión

* Provocar a demanda los escenarios de falla: cuarentena (RF-28), parseo (RF-21), publicaciones muertas y errores del marketplace.
* Repetir exactamente un escenario entre revisiones y en el CI.
* Que el matching se ejercite contra datos reales de un lado: los SKU del catálogo salen del feed real.
* Aportar corrupciones sintéticas al dataset de ML en M5, separando las usadas para entrenar de las usadas para evaluar (ADR-0003).

## Opciones consideradas

* **Opción A**: Generadores configurables con semilla, que registran la configuración usada junto a cada escenario.
* **Opción B**: Editar a mano copias de archivos reales para cada prueba.
* **Opción C**: Usar un dataset público de catálogos o inventarios.

## Decisión

Opción elegida: "Opción A: generadores configurables con semilla", porque es la única que hace los escenarios repetibles y controlables.

* **Generador de feeds (RF-37):** volumen, separador, encabezado, filas corruptas, deriva de stock, truncado y ceros en masa.
* **Generador de catálogo (RF-36):** tiendas, publicaciones por tienda, proporción de SKU coincidentes con el feed real, publicaciones muertas, latencia y tasa de error. Los SKU se muestrean de un snapshot real de Celesa, que no se versiona.
* La misma semilla y la misma configuración producen el mismo archivo. Ambos corren a demanda, sin un servidor permanente.

### Consecuencias

* A favor, porque los caminos de falla tienen tests reproducibles en el CI.
* A favor, porque el catálogo sintético se cruza contra SKU reales, y el matching no se prueba solo contra datos inventados.
* En contra, porque los datos sintéticos pueden no representar las anomalías reales. Por eso RNF-17 evalúa el modelo sobre modos no vistos y declara qué parte es sintética.

### Confirmación

* Repetir una semilla y una configuración produce el mismo resultado.
* Un feed truncado y uno con ceros en masa del generador entran en cuarentena (criterio de salida de P2).

## Ventajas y desventajas de las opciones

### Opción A: Generadores con semilla

* A favor, porque controla entradas y fallas de forma repetible.
* En contra, porque hay que construir y mantener los generadores.

### Opción B: Editar archivos a mano

* A favor, porque un caso puntual se prepara rápido.
* En contra, porque no se puede reproducir ni saber exactamente qué se cambió, y el CI no lo puede regenerar.

### Opción C: Dataset público

* A favor, porque son datos que no hay que inventar.
* En contra, porque no hay datasets públicos con el contrato de MercadoLibre ni con las fallas que hay que provocar, y sus SKU no cruzarían con el feed real.

## Más información

* Relacionado con RF-21, RF-28, RF-36, RF-37, RNF-17 y ADR-0001, y con P1, P2 y M5 del ROADMAP.
* Basado en las propuestas de Francisco Ortega para el generador de feeds y el de catálogo.
