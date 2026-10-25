# ADR-0011: Observabilidad por servicio con logs estructurados, métricas, health checks y un observador externo

## Contexto y problema

Una actualización de stock atraviesa varios servicios y puede quedar pendiente durante horas por la cuota. El usuario necesita saber qué vínculos no se actualizaron y por qué, y el equipo necesita evidencia de que se cumplen los objetivos de latencia y disponibilidad (RNF-01, RNF-19) que no dependa de lo que el propio sistema dice de sí mismo. Hay que decidir cómo se observa el sistema.

## Factores de decisión

* Seguir una corrida de punta a punta, por corrida, tarea y vínculo (RF-30, RNF-09).
* Estado por feed y por tienda en el tablero de salud (RF-31, RF-33).
* Medir RNF-01 y RNF-19 con un observador externo al sistema (PRD §4).
* No exponer secretos en logs (RNF-07) ni volver a construir el historial completo que se recortó.

## Opciones consideradas

* **Opción A**: Logs estructurados, métricas y health checks en cada servicio, más un observador externo para las mediciones de cumplimiento.
* **Opción B**: Solo logs de texto locales y una pantalla de estado general.
* **Opción C**: Una plataforma de observabilidad gestionada.

## Decisión

Opción elegida: "Opción A: observabilidad por servicio con observador externo", porque permite distinguir fallas externas, fallas propias y atraso, y medir los objetivos con evidencia independiente.

* **Logs:** JSON por la salida estándar, con identificador de corrida, tarea y vínculo en cada línea, para correlacionar entre servicios. Los 429 de MercadoLibre quedan acá, como diagnóstico técnico (RF-24).
* **Métricas:** cada servicio expone un endpoint de métricas con lo que define RF-33: corridas por proveedor, tareas pendientes y en dead letter por tienda, uso de cuota y latencia de propagación.
* **Health checks:** cada servicio expone su estado para `docker-compose` y para las sondas de RNF-19.
* **Observador externo:** un proceso aparte registra el drenado de la cola contra el simulador y ejecuta las sondas de 24 horas. Sus resultados son la evidencia de RNF-01 y RNF-19.
* La herramienta para visualizar métricas se elige en M6. El tablero de la interfaz lee la copia de estado de la API (ADR-0007), no el motor.

### Consecuencias

* A favor, porque cada falla se puede seguir de la corrida a la tarea y al vínculo afectado.
* A favor, porque los objetivos se miden desde afuera: el sistema no se califica a sí mismo.
* En contra, porque hay que instrumentar cada servicio y mantener el observador.

### Confirmación

* Una corrida se sigue en los logs de ingesta, comparador y publicación con el mismo identificador.
* Las métricas de tareas aplicadas coinciden con lo que registra el simulador.
* En M8, las sondas de 24 horas reportan la disponibilidad de la API y del motor por separado.

## Ventajas y desventajas de las opciones

### Opción A: Logs, métricas, health checks y observador externo

* A favor, porque cubre diagnóstico y medición de cumplimiento.
* En contra, porque agrega instrumentación en cada servicio.

### Opción B: Solo logs locales

* A favor, porque no requiere trabajo extra.
* En contra, porque no explica fallas parciales ni da evidencia de los objetivos.

### Opción C: Plataforma gestionada

* A favor, porque trae visualización y alertas listas.
* En contra, porque suele requerir cuentas pagas o enviar datos afuera, y no se levanta localmente sin credenciales (RNF-10).

## Más información

* Relacionado con PRD §4 y §5, RF-24, RF-30 a RF-33, RNF-01, RNF-09 y RNF-19, y con M6 y M8 del ROADMAP.
* El monitoreo del modelo de ML se define en ADR-0003.
* Basado en la propuesta de Francisco Ortega.
