# Ivo Stock: propuesta de producto

Un vendedor que opera varias tiendas necesita ofrecer en ellas el inventario de sus proveedores. Mantener una integración distinta para cada par duplica lecturas y lógica y dificulta detectar publicaciones desactualizadas.

Ivo Stock centraliza el inventario del proveedor y lo distribuye a las publicaciones vinculadas. Incorporar una fuente o una tienda consiste en cargar configuración, revisar el catálogo y aprobar coincidencias por SKU. El operador puede consultar qué stock se desea publicar, cuál fue confirmado y qué trabajo espera o falló.

Los proveedores publican un inventario completo mediante HTTP con encabezado `SKU;stock`. El motor lo consulta cada cinco horas, conserva una copia, valida sus cambios y publica diferencias. Las corridas sospechosas quedan en cuarentena. Los errores de escritura se reintentan o quedan registrados para revisión humana. Apagar un vínculo o dar de baja una fuente exige confirmar stock cero antes de desactivarlo.

El proyecto utiliza datos reales archivados de Celesa y un marketplace simulado con publicaciones preparadas, límite de llamadas y errores controlables. El POC se opera por línea de comandos. El MVP incorpora una aplicación autenticada para configurar y observar dos tiendas de 1.000 vínculos cada una. Agregar la segunda tienda reutiliza el mismo inventario, sin duplicar su ingesta.

La ingeniería se concentra en persistencia, consistencia eventual, idempotencia, recuperación, límites de una API y observabilidad. Se medirá disponibilidad funcional durante veinticuatro horas. El componente de ML del MVP está pendiente de definición.

El sistema ofrece la cantidad completa en cada tienda; la sobreventa por ventas simultáneas es un riesgo aceptado. Las fuentes degradadas conservan su último stock publicado hasta que se recuperen o el operador decida darlas de baja.

El [PRD](PRD.md) define los requisitos y la aceptación. El [SRD](../srd/SRD.md) explica el diseño y el [roadmap](../roadmap/ROADMAP.md) registra implementación y evidencia.
