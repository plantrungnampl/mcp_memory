FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV PATH="/app/apps/mcp-api/.venv/bin:$PATH"
ENV PORT=8010

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY apps/mcp-api/pyproject.toml apps/mcp-api/uv.lock ./apps/mcp-api/
COPY apps/mcp-api/README.md ./apps/mcp-api/README.md
COPY apps/mcp-api/vendor ./apps/mcp-api/vendor
COPY apps/mcp-api/migrations ./apps/mcp-api/migrations
COPY apps/mcp-api/scripts ./apps/mcp-api/scripts
COPY apps/mcp-api/src ./apps/mcp-api/src

WORKDIR /app/apps/mcp-api

RUN uv sync --locked --no-dev

EXPOSE 8010

CMD ["uvicorn", "viberecall_mcp.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8010"]

