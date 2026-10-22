# ADR-0004: Python con FastAPI para la API, los workers y el simulador

## Contexto y problema

El sistema tiene varios componentes que hay que programar: la API core, los workers de ingesta, comparación, publicación y catálogo, el simulador de MercadoLibre, los dos generadores sintéticos y, en M5, el pipeline de Machine Learning. El frontend queda fuera de esta decisión: el POC no tiene interfaz gráfica y la interfaz web llega en M1, con su propio ADR.

Hay que elegir el lenguaje y el framework web antes de empezar P0, porque de esa elección dependen la estructura del repositorio, las imágenes de Docker, el CI y los tests de todos los hitos. El plazo es corto: el POC se entrega el 27 de octubre y el MVP el 24 de noviembre.

El trabajo del dominio es parseo de archivos de texto, clientes HTTP, acceso a PostgreSQL y cálculo de diferencias sobre unas 255.000 filas por corrida. Ninguna parte es intensiva en CPU: el cuello de botella del sistema es la cuota de 60 llamadas por minuto por tienda de MercadoLibre (S-08), no la velocidad de cómputo propia.

## Factores de decisión

* **Un solo lenguaje para todo el sistema.** La defensa es individual y cada integrante debe poder explicar el sistema completo. Dos lenguajes duplican herramientas, convenciones y tests.
* **Reutilizar lo que ya existe.** `scripts/analizar_feed.py` está en Python e implementa el coeficiente de CU-07 que P2 necesita para la cuarentena (RF-28).
* **El componente de ML (M5)** se entrena, se sirve y se monitorea en el mismo sistema, y el ecosistema de ML de referencia es Python.
* **Contrato legible por máquina.** RNF-16 exige describir la API en OpenAPI.
* **Rendimiento suficiente:** una corrida de 255.000 SKU en menos de 10 minutos (RNF-02).
* **Velocidad de desarrollo** en un plazo de semanas.

## Opciones consideradas

* **Opción A**: Python 3.12, con FastAPI para la API core y el simulador, y workers como procesos Python.
* **Opción B**: Node.js con TypeScript, con Fastify o NestJS.
* **Opción C**: Go.
* **Opción D**: Java o Kotlin con Spring Boot.
* **Opción E**: combinación: API y workers en Node.js, ingesta y ML en Python.

## Decisión

Opción elegida: "Opción A: Python 3.12 con FastAPI", porque es la única que cubre todos los componentes, incluido el ML de M5, con un solo lenguaje, y permite reutilizar desde el primer día el código que ya calcula el coeficiente de CU-07. FastAPI genera la descripción OpenAPI a partir del código, lo que resuelve RNF-16 sin trabajo adicional.

Las bibliotecas de base son Pydantic para validar datos, SQLAlchemy con Alembic para el acceso a PostgreSQL y las migraciones, httpx como cliente HTTP, pytest para los tests y ruff para el formato y el análisis estático. Cambiar una biblioteca no requiere un ADR nuevo. Cambiar el lenguaje o el framework web sí.

### Consecuencias

* A favor, porque los ocho componentes comparten lenguaje, herramientas de test y convenciones: cualquiera de los tres puede leer y explicar cualquier parte.
* A favor, porque la cuarentena de P2 parte del coeficiente ya implementado en el script, en lugar de reescribirlo.
* A favor, porque M5 no exige integrar otro lenguaje: entrenamiento, serving y monitoreo usan las mismas imágenes y el mismo CI.
* A favor, porque la API documentada en OpenAPI sale del código (RNF-16) y los modelos de Pydantic validan las entradas en todas las interfaces expuestas.
* En contra, porque Python es más lento que Go o Java en cómputo puro. No afecta a este sistema: el límite es la cuota de MercadoLibre, y RNF-02 se verifica en P2 con el feed real.
* En contra, porque el tipado es opcional. Se mitiga con anotaciones de tipos y el chequeo de ruff en el CI.
* Neutral, porque el frontend se decide en M1 y puede usar otro lenguaje: se comunica con la API solo por HTTP.

### Confirmación

* P0 cierra con el CI corriendo ruff y pytest sobre `main`.
* P2 mide una corrida real de Celesa contra el límite de RNF-02. Si no lo cumple, primero se perfila el parser antes de reconsiderar esta decisión.

## Ventajas y desventajas de las opciones

### Opción A: Python 3.12 con FastAPI

* A favor, porque cubre API, workers, simulador, generadores y ML con un solo lenguaje.
* A favor, porque reutiliza el script de análisis del feed.
* A favor, porque FastAPI genera OpenAPI y valida entradas sin código adicional.
* En contra, porque el rendimiento de cómputo es menor, aunque no es el cuello de botella.

### Opción B: Node.js con TypeScript

* A favor, porque TypeScript tiene tipado estático y el ecosistema web es amplio.
* A favor, porque compartiría lenguaje con un frontend en JavaScript.
* En contra, porque el ML de M5 obligaría a sumar Python igual, o a usar bibliotecas de ML menos maduras.
* En contra, porque el coeficiente de CU-07 habría que reescribirlo.

### Opción C: Go

* A favor, porque es rápido, con binarios livianos y concurrencia simple.
* En contra, porque el rendimiento extra no se aprovecha: el límite es la cuota externa.
* En contra, porque el ML de M5 obligaría a sumar otro lenguaje.
* En contra, porque exige más código para tareas que en Python son directas, en un plazo de semanas.

### Opción D: Java o Kotlin con Spring Boot

* A favor, porque es un ecosistema maduro y robusto para servicios.
* En contra, porque la configuración y el tiempo de arranque son mayores, y el ML sigue requiriendo otro lenguaje.
* En contra, porque el volumen de código y de configuración no se justifica para el alcance.

### Opción E: Node.js para API y workers, Python para ingesta y ML

* A favor, porque usa cada lenguaje donde es más fuerte.
* En contra, porque duplica herramientas, CI, imágenes y convenciones, y obliga a cada integrante a dominar dos lenguajes para defender el sistema completo.
* En contra, porque la ingesta y el comparador comparten el modelo del estado vigente, y partirlos entre lenguajes duplica ese modelo.

## Más información

* Relacionado con RNF-02, RNF-10, RNF-12, RNF-16, RF-28 y el componente de ML (PRD §10, ADR-0003).
* El framework del frontend se decide en M1, cuando se construye la interfaz web.
