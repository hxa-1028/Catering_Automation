# Catering Proposal AI Agent

An AI-assisted catering sales-proposal platform that produces source-backed,
human-reviewed draft proposals. The system must never guess prices, menus,
venue requirements, or other business facts.

## Current status

Phase 1 establishes the Python application foundation. It provides settings,
structured redacted logging, and a minimal FastAPI health surface. It does not
yet contain catalog data, pricing, LLM calls, proposal generation, customer
enquiry routes, or deployment infrastructure.

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

`GET /healthz` reports application liveness. `GET /readyz` intentionally
returns `503` until the future database and document-conversion dependencies
are configured.
