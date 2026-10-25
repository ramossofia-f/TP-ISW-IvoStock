# ADR-0001: Python y FastAPI

Estado: aceptado. Fecha: 25/10/2026.

## Contexto

API, workers, simulador y herramientas comparten reglas y estructuras de inventario. El equipo necesita probar el circuito y preparar un componente de ML para el MVP.

## Alternativas

- Python con FastAPI y bibliotecas SQL/HTTP: un lenguaje para servicios, datos y herramientas.
- TypeScript con un framework de API: buenas herramientas de interfaz, pero separa el entorno del procesamiento de datos.
- Django: integra administración y autenticación, con mayor acoplamiento al framework para los workers.

## Decisión

Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, psycopg, httpx y boto3. CLI con argparse; servicios de aplicación reutilizables. Dependencias resueltas en `uv.lock`.

## Consecuencias y comprobación

Los workers no dependen del servidor HTTP. Las operaciones bloqueantes tienen procesos separados. Se comprueban importación del paquete, CLI, pruebas, análisis estático y construcción de la imagen. El contrato HTTP publicado corresponde a endpoints implementados.
