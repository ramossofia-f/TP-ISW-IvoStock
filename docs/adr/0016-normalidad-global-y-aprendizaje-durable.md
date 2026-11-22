# ADR-0016: Detector global de normalidad y aprendizaje durable

Estado: aceptado el 22/11/2026, con la evaluación de sensibilidad de la última sección. Propuesto
el 17/11/2026. Reemplaza el modelo binario del [ADR-0015](0015-detector-de-feeds-anomalos.md) y
conserva su guarda obligatoria y su rol monótono.

## Contexto y alternativas

RF-27 exige entrenamiento reproducible, inferencia y monitoreo. Se decide aprender exclusivamente
de las corridas aceptadas como referencia de normalidad. Esa aceptación es una etiqueta asumida,
no una confirmación independiente de calidad. El diseño anterior requería ejemplos defectuosos y
usaba ejemplos de ambas clases. Se conserva su regla de seguridad: ML sólo agrega cuarentenas
a la guarda fija. Cambiar la forma de aprender no exige retirar esa protección.

Se compararon regresión logística/perceptrón binario, que requieren ambas clases; un detector por
proveedor, que fragmenta modelos y operación; y un detector de normalidad global. Se elige
OneClassSVM con RBF: aprende una frontera no lineal de observaciones sanas, admite pesos y permite
exportar su función como JSON. Un detector lineal no representa las interacciones entre proveedor
y estadísticas. Un entrenamiento sincrónico demoraría la publicación; una cola en memoria perdería
aceptados durante una caída. Se usa una outbox en PostgreSQL.

## Decisión

- Un solo modelo global recibe el ID estable del proveedor mediante one-hot y siete estadísticas:
  filas, SKU, cantidad de descartes, tasa de errores, D, Z y p. Los conteos usan log1p y las variables
  numéricas se estandarizan con media y desviación ponderadas. No se recupera el CSV previo ni se
  incorporan las variables adicionales del experimento anterior.
- OneClassSVM usa inicialmente nu=0,05 y gamma=scale. Una distancia firmada menor que -1e-8 se
  considera anomalía. No es una probabilidad de corrupción ni acredita una tasa de aciertos.
- La guarda p>0,5 es obligatoria y se evalúa primero: si rechaza, no se consulta ML. Si pasa,
  ML puede agregar cuarentenas cuando la versión activa contiene diez aceptados del proveedor.
  Cuarentena = guarda o ML; ningún modelo, aprobación ni replay omite la guarda. Antes del
  calentamiento, si ML no responde en un segundo total o su respuesta/modelo es inválido,
  decide sólo la guarda y se registra el motivo del respaldo.
  El formato del archivo siempre se valida. La tasa mayor al 10 % genera alerta, no un bloqueo
  directo por ese umbral. ML puede considerarla junto al resto de las entradas.
- Sólo después de aceptar se guardan juntos inventario, corrida, evento de comparación y una
  observación única por corrida. Comparación y aprendizaje progresan independientemente.
- Un trabajador serializado por advisory lock global reentrena por observación pendiente, usando
  hasta 200 procesadas por proveedor y la actual. Las observaciones conservan su fecha original;
  el peso cae a la mitad cada siete días, respecto de la aceptación más reciente de la ventana.
  No se borra el historial. No hay importación automática de corridas anteriores al despliegue.
- Modelo, observaciones empleadas, hash del conjunto, versiones de bibliotecas y transformaciones
  se guardan en versiones inmutables JSON en PostgreSQL. La publicación de la versión y la
  confirmación del aprendizaje comparten transacción. Sin pickle. Un fallo conserva el modelo
  anterior y el pendiente; reintenta a los treinta segundos. Una caída indefinida no frena el motor.
- El servicio de inferencia y el entrenador corren separados. Sólo el entrenador instala sklearn.
  La inferencia ejecuta la función RBF exportada en Python puro; las peticiones internas requieren
  un secreto de entorno y no contienen el CSV, la URL ni credenciales del proveedor.
- Cada corrida conserva decisión, origen, versión y motivo del respaldo dentro de métricas
  privadas. La app sólo agrega un aviso de proveedor/corrida en cuarentena. El diagnóstico queda
  en la CLI. Las sondas de proceso, inferencia y entrenamiento se observan por separado; el
  funcionamiento por respaldo no acredita disponibilidad de ML.

## Consecuencias y comprobación

Se conservan la guarda obligatoria y el rol monótono del ADR anterior. Una cuarentena no cambia
inventario ni produce tareas o aprendizaje. Un replay vuelve a evaluar con
la versión vigente y conserva su referencia original. La identidad de aprendizaje es la corrida:
reintentar su procesamiento no duplica el trabajo; una nueva corrida estable sí es una observación.

Aprender de las propias aceptaciones puede reforzar errores y frenar novedades legítimas. Las
estadísticas elegidas no detectan alteraciones de cantidades positivas que conserven volumen,
ausencias, ceros y errores. No se presume rendimiento ilimitado: la ventana acota muestras por
proveedor y el costo depende también de la cantidad de proveedores. Las versiones y observaciones
deben incluirse en el respaldo de PostgreSQL.

Se comprueban coincidencia con sklearn, reproducción con el mismo conjunto/configuración,
ponderación temporal, calentamiento por proveedor, autenticación, plazo total y aislamiento de
métricas; luego aceptación/publicación/aprendizaje, cuarentena, caída indefinida y recuperación,
incluidos cierres abruptos antes y después de publicar el modelo. La evaluación del ADR-0015
permanece identificada como histórica y no se atribuye al nuevo detector.

La evaluación inicial de normalidad registra 8 % de falsas cuarentenas estables y 81 % de detección
de truncamientos leves; no demuestra una mejora sobre la logística. Los conjuntos, variables y
protocolos difieren del ensayo anterior: no constituyen una comparación controlada. Se publican
también resultados de guarda o ML. Conservar la guarda evita perder sus rechazos, pero no reduce
las falsas cuarentenas que agregue ML. No se declara cumplido el presupuesto de falsas cuarentenas
del ADR-0015.

## Elección frente al detector binario

Se acepta este detector y no el binario del ADR-0015 por tres razones:

- **Aprende de corridas reales.** El binario necesita ejemplos defectuosos etiquetados, que sólo
  existen en el generador sintético; su mejor variable, la concentración de ausentes al final del
  archivo, depende de que el generador trunque por la cola y de que el proveedor conserve el
  orden, algo que no se pudo verificar con un solo snapshot real. Este detector aprende de las
  aceptaciones de cada proveedor y no supone cómo son los defectos.
- **Está en producción completa.** Entrenamiento asíncrono y durable, versiones reproducibles,
  servicio de inferencia separado, respaldo por reglas y monitoreo; el binario quedó como
  entrenamiento y evaluación fuera de línea.
- **La guarda limita su riesgo.** Como sólo suma cuarentenas, un error del modelo nunca acepta lo
  que la guarda frena.

El costo aceptado son las falsas cuarentenas en corridas normales. Se evaluó si es un problema de
calibración variando `nu`, con el mismo protocolo de [la evaluación](../entregas/ML-NORMALIDAD-EVALUACION.md)
(`uv run --group ml python scripts/ml_evaluar_normalidad.py --nu VALOR`), decidiendo con guarda o ML:

| `nu` | Falsas cuarentenas en corridas estables | Truncamientos leves detectados | Truncamientos, ceros masivos y filas corruptas |
|---|---:|---:|---:|
| 0,005 | 6 % | 80 % | 100 % |
| 0,01 | 6 % | 80 % | 100 % |
| 0,02 | 7 % | 81 % | 100 % |
| 0,05 (vigente) | 8 % | 81 % | 100 % |
| 0,10 | 19 % | 85 % | 100 % |

Bajar `nu` sólo quita dos puntos: el piso de alrededor de 6 % viene de aprender únicamente de
aceptados, no de la calibración. Se conserva `nu = 0,05`. Una falsa cuarentena no publica nada:
el proveedor queda degradado con un aviso al operador y la corrida siguiente vuelve a evaluarse.
Los agotamientos masivos y las depuraciones legítimas también quedan en cuarentena, igual que con
la guarda sola; aprender esas novedades exigiría una aprobación manual, que el PRD descarta.

La reproducción es exacta en una misma plataforma: el mismo conjunto, la misma configuración y las
mismas bibliotecas dan la misma versión. Entre arquitecturas distintas (por ejemplo, x86 y ARM) la
aritmética de punto flotante del entrenamiento cambia los últimos decimales de los coeficientes y,
con ellos, el hash de la versión, aunque las decisiones de la evaluación coinciden. Por eso se
versiona el modelo entrenado y no se lo recalcula al desplegar.
