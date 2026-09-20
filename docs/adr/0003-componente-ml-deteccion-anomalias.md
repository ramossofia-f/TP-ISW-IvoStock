---
status: Aceptado
date: 2026-09-20
decision-makers: Ramos, Sarachaga, Ortega
consulted:
informed:
---

# ADR-0003 — Componente de ML: detección de anomalías en corridas de feed

## Context and Problem Statement

La Entrega 3 exige un pipeline de ML reproducible, con entrenamiento, serving y monitoreo. El documento de validación dejó dos candidatos abiertos y hay que elegir uno antes de cerrar la Entrega 1.

El alcance del proyecto restringe mucho el espacio de opciones. El sistema no gestiona ventas, así que no tiene la señal que haría obvio cualquier modelo de demanda: los únicos datos propios son el histórico de snapshots crudos del feed y la auditoría de escrituras al marketplace. Además, el catálogo del lado tienda es sintético, de modo que todo lo que dependa de atributos reales de publicaciones queda sin datos verdaderos sobre los que entrenar.

Hay un antecedente que condiciona la decisión: el PRD ya define en CU-07 un **coeficiente de sospecha** con **tolerancias fijas** que decide si una corrida entra en cuarentena. Ese coeficiente no es un placeholder a la espera de un modelo. El modelo **no lo reemplaza ni recalibra sus tolerancias**: el coeficiente queda como baseline contra el cual medir y como **fallback permanente**, y sigue decidiendo por defecto mientras no exista un modelo entrenado y válido.

## Decision Drivers

* El modelo debe alimentarse de datos que el sistema ya genera por diseño, sin incorporar fuentes nuevas.
* Debe engancharse con un caso de uso que el PRD ya tiene, en lugar de obligar a inventar uno para justificar el ML.
* Los resultados tienen que ser honestos y verificables, no fabricados para la demo: la consigna lo exige y es criterio de evaluación.
* Las tolerancias de CU-07 son fijas. El modelo compite contra ese baseline; no lo ajusta.
* El sistema tiene que seguir funcionando sin modelo, y decidir con el baseline cuando el modelo no esté disponible o sea inválido.
* Equipo de 2–3 personas, sin costos significativos y sin servicios siempre encendidos.
* La inferencia no puede comprometer RNF-02 (una corrida de 650.000 SKU procesada en menos de 10 minutos).

## Considered Options

* **Opción A1** — Detección de anomalías **supervisada liviana** sobre señales de la corrida.
* **Opción A2** — Detección de anomalías **no supervisada** sobre las mismas señales.
* **Opción B** — Predicción de quiebre de stock por SKU.
* **Opción C** — Emparejamiento SKU ↔ publicación con ML.
* **Opción D** — LLM como juez de corridas.

## Decision Outcome

Chosen option: "Opción A1 — detección de anomalías supervisada liviana", con **A2 como modelo de comparación** si el tiempo lo permite. Es la única que se apoya en datos que el sistema ya produce, se engancha con un caso de uso existente (CU-07, RF-28) y tiene un baseline contra el cual medirse de forma honesta. B y C fallan por falta de datos reales; D no es reproducible ni auditable, que es justamente lo que se evalúa.

El modelo estima un puntaje `p_ml ∈ [0,1]` por corrida a partir de señales comparadas contra el último snapshot válido: `D`, `Z`, variación relativa de filas y de stock total, tasa de errores de parseo, y `D` restringido a los SKU con vínculo activo —es decir, la oferta que realmente se apagaría—. Es **otro estimador sobre las mismas señales**, que compite contra el noisy-OR de CU-07 sin tocar sus tolerancias.

Las etiquetas salen de tres lugares: corridas reales archivadas (se asumen normales salvo las que la operación haya puesto en cuarentena), corridas con corrupción inyectada por el generador de feeds (RF-37) separadas por modo de falla —truncado, columna de stock vacía, cambio de encoding, separador distinto—, y **negativos difíciles**: caídas grandes pero legítimas, por movimiento masivo de stock real, que el sistema tiene que saber distinguir de un feed truncado.

Las etiquetas positivas son sintéticas y se declaran como tales. Para que eso no vuelva circular la evaluación, el protocolo es:

1. **Leave-one-mode-out:** se entrena con algunos modos de corrupción y se evalúa sobre los no vistos.
2. **Negativos difíciles incluidos** en el conjunto de evaluación.
3. **Falsos positivos medidos sobre histórico real**, nunca sobre corridas sintéticas.
4. Todo resultado indica qué parte de la evaluación es sintética.

### Consequences

* Good, porque no hace falta ninguna fuente de datos nueva: el histórico de snapshots y la auditoría ya son requisitos del sistema por otras razones (RF-20, RF-30).
* Good, porque existe un baseline explícito contra el cual medir. Sin él, cualquier número del modelo sería incomparable y la evaluación, decorativa.
* Good, porque la inferencia es trivial —un puntaje por corrida, no por SKU—, así que el serving y el monitoreo son abordables para el equipo y no comprometen RNF-02.
* Good, porque el sistema no queda atado al modelo: si no está entrenado, no está disponible o es inválido, decide el baseline y la ingesta no se detiene (RF-50).
* Bad, porque las etiquetas positivas son sintéticas, con el riesgo de que el modelo aprenda el generador en lugar del fenómeno. Se acota con el protocolo de evaluación, no se elimina.
* Bad, porque **hay que empezar a archivar corridas reales ya**: sin histórico el modelo llega sin datos al MVP. La empresa ya autorizó al equipo a archivar copias históricas del feed de Celesa, así que la recolección arranca de inmediato y no queda a la espera de ningún permiso.
* Neutral, porque el aporte del modelo sobre el baseline puede resultar chico, sobre todo si las señales que más pesan siguen siendo `D` y `Z`. Ese resultado es válido y se reporta tal cual: la consigna pide honestidad, no que el modelo gane.
* Neutral, porque el modelo agrega una pieza con ciclo de vida propio —versionado, actualización y rollback (RF-52)— que el sistema antes no tenía.

### Confirmation

* `make train` reproduce el entrenamiento completo con dataset versionado y semilla fija, y devuelve las mismas métricas (RF-51).
* El informe de evaluación compara modelo y baseline **por modo de corrupción**, con los modos no vistos separados de los vistos.
* RNF-17: sobre modos de corrupción no vistos, el modelo iguala o supera el recall del baseline con una tasa de falsos positivos menor o igual, medida sobre histórico real.
* RNF-18: puntuar una corrida de 650.000 SKU agrega menos de 1 minuto al tiempo de RNF-02.
* Test del fallback: con el modelo ausente o inválido, la corrida se evalúa con el coeficiente de CU-07 y la ingesta no se detiene.
* El tablero expone tasa de cuarentenas, deriva de las señales y discrepancias entre modelo y baseline (RF-53).

## Pros and Cons of the Options

### Opción A1 — Detección de anomalías supervisada liviana

Regresión logística o árbol pequeño sobre las señales de la corrida, entrenado con corridas reales y con corrupciones inyectadas.

* Good, porque encaja exactamente en un caso de uso que ya existe (CU-07, RF-28): no hay que agregar alcance para justificar el ML.
* Good, porque el baseline noisy-OR da una vara de comparación honesta y ya implementada.
* Good, porque es interpretable: se puede mostrar qué señal pesó en cada decisión, lo que importa para defenderlo.
* Good, porque la inferencia es barata y el serving es un puntaje por corrida.
* Bad, porque depende de etiquetas positivas sintéticas y arrastra el riesgo de circularidad.
* Bad, porque si el modelo termina apoyándose en `D` y `Z`, que es lo que ya hace el baseline, el aporte marginal puede ser chico.

### Opción A2 — Detección de anomalías no supervisada

Isolation Forest o carta de control robusta sobre las mismas señales, entrenada solo con histórico real.

* Good, porque no necesita etiquetas positivas: se entrena con datos 100 % reales.
* Good, porque sirve como contraste metodológico de A1, y por eso se conserva como modelo de comparación.
* Bad, porque su **propio umbral de decisión** —el del modelo, no las tolerancias fijas de CU-07— es difícil de fijar sin positivos con los que medir.
* Bad, porque es menos interpretable, y una cuarentena que no se puede explicar es difícil de defender ante el operador y ante la cátedra.

### Opción B — Predicción de quiebre de stock por SKU

Serie temporal sobre el stock del proveedor para anticipar cuándo un SKU llega a cero.

* Good, porque las etiquetas son reales: el quiebre se observa en el histórico, sin nada sintético.
* Bad, porque sin datos de ventas la señal es débil: el sistema ve el stock caer, pero no por qué.
* Bad, porque son 650.000 series, con un costo de entrenamiento y de serving desproporcionado para el equipo.
* Bad, porque no está atado a ningún caso de uso del PRD: habría que agregar un CU y sus RF solo para darle lugar, ampliando alcance en la entrega más cargada.

### Opción C — Emparejamiento SKU ↔ publicación con ML

Resolución de identidad por título y atributos de la publicación.

* Good, porque ataca R-03, que es un riesgo real del sistema.
* Bad, porque está explícitamente fuera de alcance: S-02 asume el SKU como clave de cruce confiable.
* Bad, porque necesita atributos reales de publicaciones, y el catálogo del lado tienda es sintético. Entrenaría contra datos inventados por el propio equipo.

### Opción D — LLM como juez de corridas

Consultar un modelo de lenguaje sobre cada corrida.

* Good, porque no requiere entrenamiento propio ni dataset etiquetado.
* Bad, porque no es determinista, y una decisión de cuarentena que cambia entre corridas idénticas no es auditable.
* Bad, porque tiene costo y latencia por corrida, contra la restricción de costos y contra RNF-02.
* Bad, porque no constituye el pipeline reproducible de entrenamiento, serving y monitoreo que la Entrega 3 pide: no habría nada que entrenar ni que versionar.

## More Information

* Relacionado con PRD §10, CU-07, RF-28, RF-37, RNF-02.
* **Pendiente en el PRD:** esta decisión requiere agregar RF-49 a RF-53 (puntaje del modelo, fallback al baseline, pipeline reproducible, versionado y rollback, monitoreo) y RNF-17 y RNF-18, y cerrar §10, que hoy figura como *pendiente de definir*.
* El hito de construcción es M5 del roadmap, que depende de M4 y de que haya histórico suficiente. Si al llegar hay pocas corridas archivadas, el modelo arranca en **modo sombra** y el baseline sigue decidiendo.
* Cambiar de opción más adelante requiere un ADR nuevo y, si con eso cambia el alcance comprometido, re-validar con la cátedra.
