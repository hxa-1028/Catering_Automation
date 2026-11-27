# Catering Proposal AI Agent

An AI-assisted catering sales-proposal platform that produces source-backed,
human-reviewed draft proposals. The system must never guess prices, menus,
venue requirements, or other business facts.

## Current status

Phases 1–4 establish the Python foundation, source-backed database schema,
local-only five-service Docker runtime, and strict local catalog ingestion.
The bundled catalog is synthetic prototype data only; it is not client-ready
content. Phases 5 to 8 add deterministic catalog resolution, structured intake
clarification, schema-constrained LLM brief extraction, and a bounded pipeline
that stops for clarification or returns eligible source-backed catalog records.
Phase 9 adds LLM menu selection restricted to those eligible IDs and attaches
the exact selected-menu, venue, and regional-configuration source citations.
Phase 10 adds deterministic, source-backed baseline pricing: an explicitly
mapped menu price is multiplied by the extracted guest count and declared venue
fees are added. Missing mappings, unsupported price units, and invalid source
data stop for clarification rather than produce a guessed figure. It does not
yet provide semantic document-chunk retrieval or complete regional pricing
rules such as tax, service charge, staffing, and rounding.
A live extraction call requires an administrator-configured provider and pinned
model ID; tests never call an LLM. The product does not yet contain proposal
generation, customer enquiry routes, or installer automation.

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
uv run python -m evals.run --suite golden --mode structured
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
start. Activate the bundled synthetic test catalog only for local verification:

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml run --rm worker python -m catering_agent.knowledge.ingest --source local --path /app/data/samples
```

After a valid catalog is activated, `/readyz` returns HTTP 200. Never use the
bundled sample as business data; real client source files must be approved,
declared, and ingested through their supported adapter.
