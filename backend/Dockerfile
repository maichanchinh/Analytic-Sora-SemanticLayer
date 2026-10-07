FROM python:3.14-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/backend/.venv

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
COPY backend/api.py backend/mcp.py ./
COPY backend/dashboard/config ./dashboard/config

RUN uv sync --frozen --no-dev \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app \
    && chown -R app:app /app

ENV PATH="/app/backend/.venv/bin:$PATH"

USER app

EXPOSE 8000 8001

ENTRYPOINT ["uv", "run", "--no-sync"]
CMD ["uvicorn", "sora_semantic.api:app", "--host", "0.0.0.0", "--port", "8000"]
