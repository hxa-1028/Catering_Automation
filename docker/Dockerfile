# Pinned Python 3.12 base; review and update the digest as a deliberate change.
FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

RUN pip install --no-cache-dir "uv==0.13.0" \
    && groupadd --system --gid 10001 app \
    && useradd --system --create-home --uid 10001 --gid app app

WORKDIR /app

COPY --chown=app:app pyproject.toml uv.lock README.md ./

USER app

RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app alembic.ini ./
COPY --chown=app:app src ./src

RUN uv sync --frozen --no-dev

USER app
