# ADR-0013: Interfaz de configuración estática servida por la API

Estado: aceptado. Fecha: 11/11/2026.

## Contexto y alternativas

El RF-25 pide una interfaz autenticada para configurar proveedores, tiendas y vínculos, y el RNF-13 exige arrancar todo con un comando, sin credenciales externas. La API de configuración y las sesiones ya existen ([ADR-0010](0010-cuentas-y-sesiones.md), [ADR-0011](0011-api-de-configuracion.md)); falta el cliente. Son cuatro pantallas de formularios y tablas, sin estado compartido en el navegador.

- **Aplicación de página única (React o Vue) con servicio propio.** Se descartó: agrega una etapa de build con Node, otro contenedor y otro origen (CORS), y una cadena de dependencias que mantener, a cambio de interacciones que aquí son simples.
- **Plantillas en el servidor (Jinja).** Se descartó: mezcla presentación con la API, obliga a sesiones por cookie con protección CSRF y duplicaría la validación que ya hace la API.
- **HTML, CSS y JavaScript estáticos servidos por la propia API.** Elegida: sin build, sin servicio nuevo y con el mismo origen que la API.

## Decisión

- La interfaz vive en `src/ivostock/static/` (`index.html`, `app.js`, `styles.css`), dentro del paquete: viaja con la instalación de la imagen (`uv sync --no-editable`) y `ivostock.main` la ubica con una ruta absoluta derivada de `__file__`, sin depender del directorio de trabajo.
- La API la sirve en `GET /` y `/static/*`. Es una única ruta de entrada; no hay una segunda. Ninguna de estas rutas figura en OpenAPI, que describe la API (RNF-16), no la interfaz.
- `/` y `/static/*` son públicas, además de `GET /health` y `POST /auth/login`: contienen sólo la página de acceso y el código, ningún dato operativo (RNF-11). Todo dato llega por la API con sesión de operador y la autorización sigue decidiéndose en el servidor.
- El cliente llama a la API del mismo origen, sin prefijo. Ingresa con `POST /auth/login`, guarda el token `Bearer` en `sessionStorage` (se pierde al cerrar la pestaña y, al no usar cookies, no hay CSRF), lo valida al recargar con `GET /auth/me`, lo descarta ante cualquier 401 y lo revoca con `POST /auth/logout`.
- Todo dato de la API se inserta como texto (`textContent` o nodos de texto), nunca como HTML, y no hay manejadores ni estilos en línea. `/` responde con `Content-Security-Policy: default-src 'self'` y `frame-ancestors 'none'`, de modo que una inyección no podría ejecutar código aunque el escape fallara.
- Alcance: proveedores (alta con la URL de la fuente, tasa de errores de parseo, muestra y sugerencias; baja), tiendas (disponibles, incorporar y progreso de importación por sondeo cada 5 s mientras la vista está abierta), vinculación (sugerencias con búsqueda por SKU; aprobar la selección, las primeras N o todas) vínculos (resumen, listado paginado, apagar y reanudar) y corridas (resumen por estado, listado paginado de la más reciente a la más antigua, filtro por proveedor y actualización por sondeo cada 5 s; sólo lectura). La API aprueba «todas» y «primeras N» sobre todas las sugerencias, no sobre el filtro por SKU, así que con un filtro activo la interfaz sólo permite aprobar la selección.
- El tablero de corridas se agregó con `GET /runs` y `GET /runs/summary`, de sólo lectura. Con eso RF-25 queda cubierto: corridas, tiendas, pendientes y confirmaciones de los vínculos y sus fallas. No se muestran los intentos de publicación ni las dead letters, que siguen en la CLI. Tampoco se modifica la fuente de un proveedor (RF-04).

## Consecuencias

No hay build ni dependencias de frontend, y la interfaz se despliega con la API. A cambio, el JavaScript es más verboso que con un framework y la actualización del progreso es por sondeo, no por eventos. Cerrar la pestaña cierra la sesión. Cualquier endpoint nuevo que use la interfaz debe estar documentado en OpenAPI. Las rutas públicas de la interfaz son una excepción acotada a «todo requiere `require_operator`» y deben seguir sin servir datos.

## Comprobación

`tests/test_interface.py` verifica que `/` sirve la página sin sesión, con su política de contenido, y que ni `/` ni `/static` aparecen en OpenAPI; que no queda una segunda aplicación ni una segunda ruta; que el JavaScript no usa `innerHTML` ni equivalentes, la página no tiene manejadores ni scripts en línea, el token se guarda en `sessionStorage` y no hay sesión simulada; y que todas las llamadas de `app.js` corresponden a operaciones documentadas en OpenAPI, incluidas las de proveedores, tiendas, aprobación, vínculos y corridas. El comportamiento en el navegador no está automatizado en CI: se comprueba a mano con `make up`, abriendo `http://localhost:8000/` e ingresando con un operador de `data/operadores.txt`.
