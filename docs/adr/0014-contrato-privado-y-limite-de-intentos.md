# ADR-0014: Contrato OpenAPI privado y límite de intentos de login

Estado: aceptado. Fecha: 11/11/2026.

## Contexto y alternativas

Dos huecos quedaron tras el [ADR-0010](0010-cuentas-y-sesiones.md) y el [ADR-0013](0013-interfaz-estatica.md). FastAPI publica por defecto `/docs`, `/redoc` y `/openapi.json` sin sesión, contra la regla de que sólo `/health`, `/auth/login` y la interfaz estática son públicos (RNF-11). Y el login aceptaba intentos sin límite sobre cinco cuentas conocidas, así que la contraseña podía probarse por fuerza bruta.

Para el contrato:

- **Dejarlo público y documentarlo como excepción.** Se descartó: revela rutas, modelos y reglas de validación a quien no tiene cuenta, sin ninguna ventaja para el operador.
- **Protegerlo con la sesión.** Elegida.

Para el límite de intentos:

- **Contador en memoria del proceso.** Se descartó: se pierde al reiniciar y no se comparte entre procesos de la API.
- **Retardo creciente en cada respuesta.** Se descartó: mantiene ocupados los hilos del servidor y no frena a un atacante que paraleliza.
- **Registro de fallos en PostgreSQL, con bloqueo por usuario.** Elegida: es durable, compartida entre procesos y ya hay una base.

## Decisión

- La aplicación se crea con `docs_url=None`, `redoc_url=None` y `openapi_url=None`: no hay Swagger UI ni ReDoc. El esquema se entrega en `GET /openapi.json`, que depende de `require_operator` y no figura en el propio esquema. El simulador, que es una pieza de ensayo, conserva su documentación.
- Cada intento fallido (usuario inexistente, inactivo o contraseña errónea) inserta una fila en `login_failures` (migración 0006). Con `LOGIN_MAX_ATTEMPTS` fallos (5 por defecto) del mismo usuario dentro de `LOGIN_WINDOW_MINUTES` (15), `POST /auth/login` responde `429` con `Retry-After` hasta que el más antiguo salga de la ventana. Un acceso correcto borra los fallos del usuario.
- El bloqueo vale también para usuarios que no existen, de modo que no revela qué cuentas hay. Mientras dura no se registran más fallos, así que insistir no lo alarga, y se rechaza incluso la contraseña correcta antes de calcular el hash.
- Los intentos de un mismo usuario se serializan con un bloqueo asesor de transacción: probar contraseñas en paralelo no supera el límite. Las filas vencidas se borran en cada fallo.
- La sesión `usuario>` aplica el mismo límite, porque usa `ivostock.auth.authenticate`.

## Consecuencias

El límite es por nombre de usuario, no por origen: quien conoce un nombre de operador puede bloquearlo durante la ventana. Se aceptó porque son cinco cuentas internas y el bloqueo es corto y se levanta solo. Un límite por dirección IP exigiría confiar en cabeceras de un proxy que hoy no existe. Para consultar el contrato hay que iniciar sesión y enviar el token; la interfaz no necesita el esquema. Un `429` en la pantalla de acceso se muestra con el mensaje de la API.

## Comprobación

`tests/test_auth.py` verifica que `/docs`, `/redoc` y `/docs/oauth2-redirect` devuelven 404 y que `/openapi.json` devuelve 401 sin sesión y el esquema con ella; el bloqueo tras cinco fallos, incluso con la contraseña correcta y con `Retry-After`; que es por usuario y alcanza a nombres inexistentes; que un acceso correcto reinicia el contador; que los intentos durante el bloqueo no lo extienden; su vencimiento al pasar la ventana; los límites tomados del entorno; que `/health` y las sesiones abiertas no se afectan; y el mismo comportamiento en `usuario>`.
