# syntax=docker/dockerfile:1

###############################################################################
# Builder — resolve and install dependencies into a self-contained virtualenv
###############################################################################
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first (cached layer, independent of source changes)
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Install the project itself
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

###############################################################################
# Runtime
###############################################################################
FROM python:3.10-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8017 \
    EXCEL_FILES_PATH=/data/excel_files

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app
COPY --chown=app:app docker/healthcheck.py /usr/local/bin/healthcheck.py

# The server writes excel-mcp.log next to the package root (/app), so that
# directory itself must be writable by the unprivileged user.
RUN chown app:app /app

# Excel workbooks live here; mounted as a volume in compose
RUN mkdir -p "$EXCEL_FILES_PATH" && chown -R app:app /data

USER app

EXPOSE 8017

# The MCP endpoint answers on /mcp. Any HTTP response proves the ASGI app is
# live; only a connection failure or timeout marks the container unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "/usr/local/bin/healthcheck.py"]

ENTRYPOINT ["excel-mcp-server"]
CMD ["streamable-http"]
