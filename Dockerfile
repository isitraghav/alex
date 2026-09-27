# uv-based image. Runs the FastAPI service by default; override cmd for CLI.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project   # cache deps layer
COPY alex ./alex
RUN uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "alex-api"]
