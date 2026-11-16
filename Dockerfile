# Runs the benchmark. Pass flags after the image name, e.g. `--models a,b`.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project   # cache deps layer
COPY alex ./alex
RUN uv sync --no-dev

ENTRYPOINT ["uv", "run", "--no-dev", "alex"]
