# ADR-0007: Inventarios completos y diferencias confirmadas

Estado: aceptado. Fecha: 25/10/2026.

## Contexto y alternativas

El feed disponible enumera existencias completas y los agotados pueden desaparecer. Se comparan tratarlo como eventos incrementales, reescribir cada publicación y mantener un inventario vigente con validación y deltas.

## Decisión

Cada corrida aceptada representa el inventario completo; ausencia significa cero. Si su snapshot es idéntico al último aceptado, se reutiliza el estado sin reescribirlo y se conserva un evento durable de comparación. El contrato y la guarda determinista se definen en el [PRD](../prd/PRD.md). La comparación usa el último confirmado por vínculo. El corte explícito a cero tiene precedencia y se conserva hasta confirmación.

Para generar escenarios se comparan edición manual, datasets públicos y generador con semilla. Se elige el generador: la misma base, parámetros y semilla producen los mismos bytes. Admite volumen, truncamiento, ceros, errores y deriva, manteniendo encabezado y columnas fijos. Las variantes son sintéticas y no modifican su base. Esto permite repetir la misma falla en CI y con datos autorizados, sin suponer que representa todo el comportamiento del proveedor.

## Consecuencias

Una falla de escritura sigue siendo observable aunque el siguiente feed no cambie. La cuarentena evita aceptar desapariciones masivas sin propagar el archivo sospechoso. Una caída de fuente conserva el último publicado, con riesgo visible. No se promete eliminar sobreventa.

## Comprobación

Ausencias, cambios entre cantidades positivas, corrida estable sin escrituras, cuarentena y reanudación con el último deseado. La guarda determinista no presupone una elección de ML.
