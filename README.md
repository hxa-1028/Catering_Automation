# Catering Proposal AI Agent

An AI-assisted catering sales-proposal platform that produces source-backed,
human-reviewed draft proposals. The system must never guess prices, menus,
venue requirements, or other business facts.

## Current status

Phases 1–3 establish the Python foundation, source-backed database schema, and
local-only five-service Docker runtime. The runtime deliberately remains
unready until a later ingestion phase activates an approved catalog version.
It does not yet contain catalog data, pricing, LLM calls, proposal generation,
customer enquiry routes, or installer automation.

The product will be delivered as a dedicated, isolated deployment for each
client. The future customer intake channel is called the **Catering Enquiry
Assistant**; it will be separate from the internal proposal portal and cannot
quote, confirm availability, or issue a proposal.

## Development

Install the project dependencies with Python 3.12:

```powershell
uv sync
```

Copy `.env.example` to `.env` if local setting overrides are needed. Do not
store secrets in `.env.example` or commit `.env`.

Run the checks:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Run the development server:

```powershell
uv run uvicorn catering_agent.api.main:app --reload --host 127.0.0.1 --port 8080
```

`GET /healthz` reports application-process liveness. `GET /readyz` reports
readiness only when PostgreSQL, the Alembic head, pgvector, Gotenberg, required
file secrets, and an active catalog version are present.

## Local container runtime

Docker Desktop with the WSL2 backend is required. The stack is strictly local:
only the internal portal is published at `http://127.0.0.1:8080`; PostgreSQL
and Gotenberg have no host ports.

1. Copy `docker/.env.template` to the ignored `docker/.env` file.
2. Create the ignored `docker/secrets/db_password` and
   `docker/secrets/llm_api_key` files with the values supplied by the installing
   administrator. Do not commit these files or put the values in `.env`.
3. Start the runtime from the repository root:

   ```powershell
   docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --build
   ```

The `migrate` service must complete successfully before the app and worker can
start. Until a catalog is ingested and activated, `/readyz` correctly returns
HTTP 503 even if all containers are otherwise running.
