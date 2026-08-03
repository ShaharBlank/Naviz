FROM ghcr.io/astral-sh/uv:0.11.16 AS uv
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/README.md ./apps/api/
COPY apps/api/src ./apps/api/src
COPY apps/api/alembic.ini ./apps/api/alembic.ini
COPY apps/api/migrations ./apps/api/migrations
COPY packages/data_pipeline/pyproject.toml ./packages/data_pipeline/pyproject.toml
COPY packages/data_pipeline/naviz_data ./packages/data_pipeline/naviz_data
RUN uv sync --frozen --no-dev --no-editable --package naviz-api

RUN addgroup --system naviz && adduser --system --ingroup naviz naviz
USER naviz

ENV PORT=10000
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn naviz_api.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
