# Runs the benchmark. Pass flags after the image name, e.g. `--models a,b`.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra graph --no-install-project   # cached dependency layer
COPY alex ./alex
RUN uv sync --frozen --no-dev --extra graph \
 && useradd --create-home --uid 10001 alex && mkdir -p results && chown alex results
USER alex

# the venv is fixed at build time; run its executables directly (alex, alex-kg, alex-mcp)
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["alex"]
