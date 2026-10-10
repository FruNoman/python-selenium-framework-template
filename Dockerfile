# Test-runner image: the same thing runs in docker-compose.ci.yml, as a Kubernetes Job, or in any CI
# that can run a container. Browsers are NOT in here — they live in Selenium Grid (GRID_URL).
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /bin/uv
WORKDIR /workspace
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv

# dependencies first, so code changes don't re-install them
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV RUNNER=grid CI=true
# Results land in /workspace/build — mount or copy it out to keep reports and logs.
ENTRYPOINT ["sh", "-c", "uv run --frozen --no-dev pytest -n ${TESTS_THREADS:-3} \"$@\"", "--"]
