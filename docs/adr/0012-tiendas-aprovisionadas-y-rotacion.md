# ADR-0012: Tiendas aprovisionadas fuera de la aplicación y rotación de la importación

Estado: aceptado. Fecha: 10/11/2026.

## Contexto y alternativas

El supuesto S-01 y el criterio de aceptación 6 piden incorporar una segunda tienda desde la aplicación, reutilizando el inventario ya ingerido. En el POC, `store-add` creaba la tienda en el simulador con la credencial de control, algo que en producción no existe: la tienda ya estaría ahí. Además `import_page` elegía siempre la primera tienda por id, así que una tienda nueva esperaba a que terminara la importación de la anterior (unos 22 minutos para 127.564 publicaciones).

Para el aprovisionamiento se evaluó dejarlo en `store-add` con una opción, y se descartó porque la sesión de usuario y la API seguirían dependiendo de la credencial de control. Para el orden de importación se compararon tres criterios: por menor avance (una tienda nueva monopolizaría el worker hasta alcanzar a la otra y la demoraría), al azar (no determinista, sin garantía) y por la atención más antigua.

## Decisión

- `scripts/provisionar_tiendas.py` (módulo `ivostock.provision`) crea las tiendas en el simulador, de forma idempotente y determinista. Cada una recibe el 50 % de los SKU distintos del inventario, de los que la mitad forma un núcleo común a todas y el resto es propio de cada una; así las muestras son distintas y se solapan por construcción, y agregar una tienda al final de la lista no altera las anteriores. Falla con un error claro si no puede garantizarlo.
- `MARKETPLACE_STORES` lista las tiendas con credenciales preconfiguradas (RF-05). `services.incorporate_store`, usada por la API, `store-add` y la sesión de usuario, sólo acepta una tienda de esa lista que además responda a una lectura de negocio; nunca crea nada y no usa la credencial de control. Las incorporadas siguen funcionando aunque se retiren de la lista.
- `import_page` atiende primero a la tienda menos recientemente atendida (`stores.import_served_at`, migración 0005). Una tienda sin cupo libre en su ventana de 60 s cede el turno; si ninguna tiene, se atiende en el mismo orden y se espera, como antes. La cuota de cada tienda es independiente, así que la rotación no la compromete.
- Un 404 al importar degrada la tienda con el mensaje «La tienda no existe en el marketplace» y se reintenta a los cinco minutos, sin lanzar excepción: es esperable, no un defecto.

## Consecuencias

Dos importaciones simultáneas avanzan en paralelo, cada una limitada por su propia cuota. Incorporar una tienda requiere aprovisionarla antes en el ensayo. La consulta de cupo es orientativa: otro proceso puede consumirlo después, y `reserve` sigue decidiendo. El sondeo de existencia consume una llamada de la cuota de la tienda.

## Comprobación

`tests/test_provision.py` cubre muestras distintas, solapadas y deterministas, y el aprovisionamiento idempotente contra el simulador. `tests/test_second_store.py` verifica la alternancia de dos importaciones y su ejecución simultánea, que una tienda sin cupo no bloquea a otra, que sugerir y aprobar en la tienda nueva no descarga al proveedor ni crea corridas, que sus vínculos no tocan los de la primera, la cantidad completa del mismo SKU en ambas tiendas con un único vínculo activo por publicación (RF-08, INV-1), la independencia de la cuota por tienda en el cliente y en el simulador, y que una sola corrida actualiza ambas tiendas.
