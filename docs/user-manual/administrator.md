# Administrator guide

## Local runtime (Phase 3)

This proof-of-concept runs only on the installing machine. It does not expose
the reviewer portal to a LAN or the internet.

Before starting it, install Docker Desktop with the WSL2 backend. From the
repository root, copy `docker/.env.template` to `docker/.env`, then create the
two local secret files below. These files are ignored by Git and must be
restricted to the installing user:

1. `docker/secrets/db_password` — the generated PostgreSQL password.
2. `docker/secrets/llm_api_key` — the configured provider key. It is not used
   for proposal generation at this phase, but the runtime verifies that the
   required secret is available.

Start the services with:

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --build
```

The app is available only at `http://127.0.0.1:8080`. `GET /healthz` confirms
that its process is running. `GET /readyz` confirms the database, migration
head, pgvector extension, document converter, file secrets, and active catalog
version. It will remain `503` until an approved catalog has been ingested in a
later phase; this is expected and prevents the system from representing an
unsourced catalog as usable.

Do not publish database or document-converter ports, move secret values into
environment files, or treat this local prototype as remote production hosting.
