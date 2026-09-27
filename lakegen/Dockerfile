FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY lakegen ./lakegen

EXPOSE 8000

CMD [".venv/bin/uvicorn", "lakegen.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
