# ADR-0009: Docker Compose para el entorno local

## Contexto y problema

El sistema completo tiene que levantarse localmente con un procedimiento simple, sin credenciales de terceros, porque es el mecanismo principal de corrección de la materia (RNF-10). Eso incluye los servicios del motor, el simulador de MercadoLibre, PostgreSQL, MinIO y Redis, y desde M1 la API con su propia base. Hay que decidir cómo se describe y se levanta ese entorno.

## Factores de decisión

* Un único comando para levantar todo, documentado en el README (RNF-10).
* Las mismas imágenes y la misma configuración por entorno en local y en la nube (RNF-11).
* Poder cortar y reiniciar servicios a demanda, para la campaña de cierres abruptos de RNF-06.
* Ningún secreto en el repositorio (RNF-07).

## Opciones consideradas

* **Opción A**: Docker Compose, con un servicio por componente y volúmenes para los almacenes.
* **Opción B**: Instalación manual de cada proceso y almacén, con un instructivo.
* **Opción C**: Kubernetes local (por ejemplo kind o minikube).

## Decisión

Opción elegida: "Opción A: Docker Compose", porque describe el entorno completo en un archivo versionado y lo levanta con `make up`, sin sumar un orquestador.

* Un servicio por componente (ADR-0008) y uno por almacén, con health checks y reinicio automático de los procesos.
* Volúmenes persistentes para PostgreSQL, MinIO y Redis, que sobreviven a los cierres abruptos de las pruebas.
* La configuración se toma de un archivo `.env` que no se versiona. El repositorio incluye un `.env.example` con valores de desarrollo y sin credenciales reales.
* Desde M1, la API y el motor usan redes y bases separadas dentro del mismo archivo (ADR-0007).

### Consecuencias

* A favor, porque cualquiera, incluida la cátedra, levanta el sistema desde un checkout limpio con un solo comando.
* A favor, porque cortar un servicio es `docker compose kill <servicio>`, lo que hace reproducibles los cierres abruptos.
* En contra, porque hay que mantener el archivo al día con cada servicio nuevo.
* En contra, porque en una sola máquina no se demuestra la separación de CPU entre la API y el motor. Esa evidencia sale de la topología de dos servidores de ADR-0007.

### Confirmación

* P0 cierra con `make up` levantando PostgreSQL, MinIO y Redis desde un checkout limpio, sin credenciales externas.
* Cada hito agrega su servicio al archivo y al README.

## Ventajas y desventajas de las opciones

### Opción A: Docker Compose

* A favor, porque concentra el entorno en un archivo versionado y es el estándar para este tamaño de sistema.
* En contra, porque exige mantenerlo.

### Opción B: Instalación manual

* A favor, porque no requiere contenedores.
* En contra, porque cada máquina queda distinta y la corrección depende de seguir muchos pasos a mano.

### Opción C: Kubernetes local

* A favor, porque se parece más a un despliegue productivo grande.
* En contra, porque excede la necesidad local y suma una herramienta que el equipo tendría que aprender y la cátedra que instalar.

## Más información

* Relacionado con RNF-06, RNF-07, RNF-10 y RNF-11, y con P0 del ROADMAP.
* Basado en la propuesta de Francisco Ortega.
