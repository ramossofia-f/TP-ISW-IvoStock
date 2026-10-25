FROM ghcr.io/astral-sh/uv:0.10.4 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /work
ENV UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-editable
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs
COPY README.md CLAUDE.md COMMITS-EQUIPO.md ./
RUN useradd --create-home app && chown -R app:app /work
USER app
CMD ["ivostock", "--help"]
