# ADR-0010: Cuentas de operador precreadas y sesiones en PostgreSQL

Estado: aceptado. Fecha: 09/11/2026.

## Contexto y alternativas

RF-01 pide operadores individuales precreados y operaciones autenticadas; RNF-11 exige que configuración y estado sólo sean accesibles con sesión. El POC validaba una cuenta compartida `Admin`/`Admin` dentro de la sesión `usuario>`. Para la sesión se compararon tres alternativas:

- **JWT firmado sin estado en el servidor.** No consulta la base, pero no se puede revocar antes de vencer: un logout o la baja de un operador no cierran la sesión, y exige gestionar una clave de firma.
- **Cookie de sesión.** Sirve a una interfaz web, pero agrega CSRF y obliga a decidir la interfaz antes de tener la API.
- **Token opaco guardado como SHA-256 en PostgreSQL y enviado como `Authorization: Bearer`.** Cada petición consulta la base, que el motor ya exige (RNF-08), y a cambio la sesión se revoca al instante.

Para el alta de cuentas se evaluó crearlas por la API, pero eso exigiría una cuenta inicial privilegiada y roles, y el PRD declara los mismos permisos para todos los operadores.

## Decisión

Las cuentas se precrean: `scripts/configurar.py` genera cinco operadores con contraseñas aleatorias, deja los hashes PBKDF2 en `OPERATOR_ACCOUNTS` (`.env`) y las contraseñas en `data/operadores.txt`, ambos fuera de Git. El servicio `init` copia esos hashes a la tabla `users` en cada arranque; si un hash cambió, actualiza la cuenta y cierra sus sesiones. El formato del hash usa `:` en lugar de `$` para sobrevivir a la interpolación de `.env` por Compose.

`POST /auth/login` devuelve un token aleatorio de 256 bits; la tabla `sessions` guarda sólo su SHA-256 y el vencimiento (`SESSION_TTL_MINUTES`, 480 por defecto). La dependencia `require_operator` protege todo endpoint salvo `/health` y el login. La sesión `usuario>` y la API autentican con el mismo módulo `ivostock.auth`.

## Consecuencias

Una copia de la base no permite reutilizar sesiones ni recuperar contraseñas. Usuario inexistente, inactivo o contraseña errónea producen la misma respuesta y verifican contra un hash ficticio para igualar el tiempo. Cada petición autenticada agrega una consulta a PostgreSQL. No hay recuperación de contraseña ni límite de intentos fallidos: rotar cuentas implica regenerar `OPERATOR_ACCOUNTS`. El token se guarda en el cliente, decisión que la interfaz tomará según su diseño.

## Comprobación

`tests/test_auth.py`: login correcto e incorrecto, 401 sin token, con token desconocido o vencido, logout, baja de usuario, hashes sin texto claro en la base, logs sin contraseñas ni tokens, `/health` sin datos operativos y una prueba que recorre las rutas de la aplicación y exige 401 en todas las no públicas.
