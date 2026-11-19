# Entrega 3: demostración pendiente del modelo operativo de ML

Fecha: 17/11/2026. Entrega 3: 24/11/2026.

**Pendiente de mostrar en el video de la última entrega:** el calentamiento del detector con
las corridas del proveedor y la publicación de una versión operativa.

> Para empezar a decidir sobre un proveedor, la versión activa debe incorporar **10 aceptados suyos**.

Si al preparar la entrega no hay suficientes runs, **el modelo operativo se entrega con el feed
n.º 10 aceptado de ese proveedor**, una vez que el entrenador procese esa observación y publique
la versión que la incorpora. Aceptar la corrida n.º 10 deja el aprendizaje pendiente: por ser
asíncrono, no implica que el modelo ya esté listo en ese mismo instante. La siguiente corrida
puede incorporar la evaluación adicional de ML cuando esa versión esté activa; la guarda fija
permanece obligatoria y el modelo sólo puede sumar cuarentenas.

Durante el calentamiento deciden las reglas fijas y los aceptados se usan para aprender.
El modelo es global: las diez observaciones se exigen para habilitar la decisión sobre cada
proveedor, sin crear modelos separados. No se incluye automáticamente el historial anterior al
despliegue ni se entrega como operativo el modelo del experimento binario antiguo.

## Recorrido pendiente para el video

- Mostrar que el proveedor todavía no tiene diez aceptados incorporados y que funciona por reglas.
- Ejecutar y aceptar el feed n.º 10; observar el pendiente de aprendizaje con `ivostock ml-report`.
- Esperar el entrenamiento y mostrar la nueva versión activa con diez observaciones del proveedor.
- Ejecutar una corrida posterior que pase la guarda y comprobar la evaluación adicional de ML
  y la propagación de cambios; mostrar que ML nunca libera un rechazo de la guarda.
- Mostrar al operador únicamente el estado funcional y los avisos de cuarentena. Puntajes,
  versiones y diagnóstico de aprendizaje se muestran desde las herramientas de backend.

Se pueden usar disparos manuales de `ivostock ingest ID` para preparar la demostración sin esperar
diez intervalos de cinco horas. Deben identificarse como corridas manuales y declarar si se usan
datos archivados o variantes sintéticas; no se presentan como un histórico de producción.

**Estado:** recorrido manual y grabación pendientes. Las pruebas automatizadas del calentamiento
ya están registradas en la [verificación de ML](ML-NORMALIDAD-VERIFICACION.md), pero no sustituyen
esta demostración en el video. El comportamiento y sus límites se definen en el
[ADR-0016](../adr/0016-normalidad-global-y-aprendizaje-durable.md).
