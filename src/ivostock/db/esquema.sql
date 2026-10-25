-- Esquema de la base del motor para la ingesta (P2). Idempotente: se puede aplicar varias veces.

CREATE TABLE IF NOT EXISTS proveedores (
    id          text PRIMARY KEY,
    config      jsonb NOT NULL,
    prioridad   text NOT NULL CHECK (prioridad IN ('baja', 'media', 'alta')),
    validado_en timestamptz
);

-- Una fila por corrida, aceptada o no. El comparador toma de acá las corridas aceptadas (ADR-0006).
CREATE TABLE IF NOT EXISTS corridas (
    id             uuid PRIMARY KEY,
    proveedor_id   text NOT NULL REFERENCES proveedores (id),
    iniciada       timestamptz NOT NULL,
    terminada      timestamptz NOT NULL DEFAULT now(),
    estado         text NOT NULL CHECK (estado IN ('aceptada', 'cuarentena', 'repetida', 'fallida')),
    motivo         text,
    filas          integer NOT NULL DEFAULT 0,
    errores_parseo integer NOT NULL DEFAULT 0,
    duplicados     integer NOT NULL DEFAULT 0,
    senal_d        double precision,
    senal_z        double precision,
    coeficiente    double precision,
    snapshot_clave text,
    sha256         text,
    encoding       text
);
CREATE INDEX IF NOT EXISTS corridas_proveedor_idx ON corridas (proveedor_id, iniciada DESC);

-- Descarte trazado de RF-21.
CREATE TABLE IF NOT EXISTS corrida_descartes (
    corrida_id uuid NOT NULL REFERENCES corridas (id),
    linea      integer NOT NULL,
    motivo     text NOT NULL,
    contenido  text NOT NULL
);
CREATE INDEX IF NOT EXISTS corrida_descartes_idx ON corrida_descartes (corrida_id);

-- Estado vigente por proveedor (RF-22). Un SKU que no figura vale cero.
CREATE TABLE IF NOT EXISTS estado_vigente (
    proveedor_id text NOT NULL REFERENCES proveedores (id),
    sku          text NOT NULL,
    stock        integer NOT NULL CHECK (stock >= 0),
    corrida_id   uuid NOT NULL REFERENCES corridas (id),
    PRIMARY KEY (proveedor_id, sku)
);
