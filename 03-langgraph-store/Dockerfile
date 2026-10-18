FROM python:3.14-slim

# Copy the uv binary from its official image (a "multi-stage" style COPY)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Layer 1: dependencies only. Cached until pyproject.toml/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# Layer 2: your code. Changes often, so it comes last.
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

# Put the venv on PATH so the project script runs directly
ENV PATH="/app/.venv/bin:$PATH"

CMD ["langgraph-store-example"]