# 0. Repository Instructions

For every non-trivial task in this repository, read and follow
`workflows/taskworkflow.md` before making implementation changes.

A task is non-trivial when it requires investigation, affects more than one
file or behavior, changes architecture, data, prompts, pricing, or security,
or needs meaningful verification. One-line edits and simple factual questions
do not require the workflow.

Store durable working notes for active tasks in `workflows/tasks/<slug>/` as
described by the workflow. These notes are scratch state, not product
documentation, and that folder is Git-ignored.

The user's current request and higher-priority system instructions override
the workflow when they conflict. Do not let workflow bookkeeping delay useful
work or create an approval gate the user did not request. **Exception:** the
accuracy rules in §1-D ("Accuracy contract") and the security rules in §10 may
not be relaxed by an in-session request alone. Flag the conflict and get
explicit maintainer sign-off first.

# AGENTS.md — Catering Proposal AI Agent

This file instructs any coding agent (Cursor, Claude Code, Codex, etc.)
working in this repository. Read it fully before writing or modifying code. It
encodes the architecture and rules chosen for this project. Do not silently
deviate from them; if a deviation seems necessary, flag it to the human
maintainer and record it in the task's `04-decisions.md`.

The original client brief is `JOB DESCRIPTION.txt` at the repository root.
Treat it as read-only input and as an illustrative regional scenario—not as a
geographic, currency, language, source-system, or product-scope constraint.

> **Repository status:** greenfield. The structure in §3 and the commands in
> §4 are the target contract. Create directories and files as tasks need
> them, but follow these names and paths exactly so later tasks can rely on
> them.

---

## 1. Project Overview

### 1-A. What This Project Builds

An AI-assisted, globally deployable **catering sales-proposal platform**. It
can serve catering and events businesses in any supported country or region,
using each customer's approved local catalog, policy pack, templates,
currencies, languages, and regulatory/business requirements.

The San Francisco Bay Area scenario in `JOB DESCRIPTION.txt` is a sample
prototype dataset only. It must not become a hard-coded product assumption.

A salesperson describes an event in a language supported by the selected
regional specification, for example:

> "The client is planning a 150-person wedding at the Brazilian Room in
> September and would like a cocktail reception followed by a seated dinner."

The system then:

1. extracts a structured event brief (client, date, venue, guest count, event
   type, service style, menu preferences, other requirements);
2. resolves the correct **venue** and its venue-specific proposal template;
3. offers the eligible **seasonal/event menus** for that venue, date, and
   service style;
4. retrieves the relevant facts from approved company documents (venue
   requirements, inclusions, policies);
5. applies **pricing and business rules** deterministically;
6. populates client and event information;
7. renders a professionally formatted **DOCX (and PDF) draft proposal**; and
8. presents it to a **salesperson for review, edits with reasons, and
   approval** before anything leaves the company.

The first deliverable is a **proof of concept** on a limited dataset:
3 venues, about 5 representative menus, the relevant pricing data, and about
10 completed proposals used as a golden evaluation set. If it succeeds, the
system will be expanded to the full venue/menu/pricing library and production
sales workflows.

#### Global and regional configuration contract

Every customer organization configures one or more versioned
`RegionalSpecification` records. A specification is the only source of
regional behavior and identifies:

- `region_spec_id` and `version`;
- ISO 3166 country/subdivision identifiers, locality, tax jurisdiction(s), and
  IANA timezone;
- BCP 47 language/locale and supported document languages;
- ISO 4217 currency and locale-specific decimal, grouping, date, time, and
  address display rules;
- the applicable regional catalog, menu taxonomy, templates, and approved
  policy/rule versions;
- authoritative sources for tax, food safety, allergen, licensing, labor,
  service-charge, deposit, and other applicable business rules; and
- the effective-date window and source references for all of the above.

The selected regional specification is determined by explicit, approved
organization/venue configuration and confirmed event location—not by the
client's name, language, IP address, model knowledge, or a fuzzy geographic
guess. If several specifications match, none match, or the event spans
jurisdictions without an approved configuration, the proposal moves to
`NEEDS_CLARIFICATION`.

“Suggest” always means “rank or present candidates already eligible under the
selected regional specification.” It never means inventing regional cuisine,
customs, legal obligations, prices, taxes, translations, dietary advice, or
menu items.

### 1-B. Target Users

| Role | Description | Assumed skill level |
|---|---|---|
| **Salesperson** | Enters event briefs, answers clarification prompts, reviews drafts | Comfortable with a web browser; not technical |
| **Reviewer / approver** | Often the same salesperson or a sales lead; checks every line item against its source, records overrides, approves | As above; owns the business accuracy of the final proposal |
| **Installing administrator** | Office IT person or the developer; installs the system and configures source/identity adapters, regional specifications, and the LLM provider | Can follow a wizard and supported-language instructions; cannot debug Docker/WSL internals |
| **Regional content owner** | Maintains the pricing workbooks, menus, templates, translations, and regional policy sources for a supported location | Business user; must never be asked to edit data in a format other than their existing Word/Excel files |

### 1-C. Platform

- **Host OS (prototype):** Windows 10 build 19041 (2004) or later, or
  Windows 11, on a single office machine. No Linux/macOS installer in this
  phase. Developers may run the Python app natively on any OS for development.
- **Runtime:** Docker Desktop with the WSL2 backend. The host never gets
  Python, PostgreSQL, or LibreOffice installed directly.
- **Access:** the reviewer UI is a web app at `http://127.0.0.1:8080`, which
  is localhost only in v1 (see §16).
- **Business systems:** the core uses a source-storage and identity abstraction.
  A local filesystem is supported for development, and Microsoft 365
  (SharePoint/OneDrive through Microsoft Graph; Microsoft Entra ID for review
  identity) is the first enterprise connector. A customer's sources,
  authentication provider, and data residency requirements are configuration,
  not regional assumptions baked into business logic.
- **AI provider:** Anthropic Claude API (default) or OpenAI API, behind a
  provider abstraction. Selected by configuration, not code.
- **Regional portability:** the containerized application and domain model are
  region-neutral. The Windows/Docker installer is the initial deployment
  package; it must not constrain which countries, currencies, languages, or
  regional catalogs the application can support.

### 1-D. Full Product Specification

This section is the product specification for v1 (the proof of concept). If a
later `docs/spec.md` is created, it supersedes this section for *what* to
build; the rest of this file still governs *how* to build it.

#### Accuracy contract (non-negotiable)

The client's single most important requirement is: **the system must not
guess pricing, menu items, venue requirements, or other business
information.** That requirement translates into these engineering rules:

1. **Structured data is not RAG.** Prices, menus, menu items, venue
   capacities, fees, minimums, tax rates, currencies, staffing ratios, and
   regional requirements are ingested from approved sources into **typed
   relational tables** and read by exact key plus regional specification and
   effective date. Vector search is used only for unstructured narrative
   content (venue policies, inclusions, past-proposal phrasing), and anything
   it returns is cited, not paraphrased into a fact.
2. **The LLM never produces business values.** The LLM is allowed to:
   - extract an `EventBrief` from free text, via schema-constrained tool
     calling;
   - choose among **candidate IDs supplied by deterministic code** (e.g.
     which of 4 eligible menus best fits "light, Mediterranean"), with output
     validated against that candidate list; and
   - draft short narrative sections (cover letter paragraph), clearly marked
     as AI-drafted in the review UI.

   It is never allowed to emit a price, quantity, total, menu item name or
   description, venue fact, or policy text that ends up in a proposal.
3. **Every proposal value carries provenance.** Each line item, menu item,
   venue fact, and computed figure has a `source_ref` that records the source
   provider-specific source ID, file content hash, sheet/cell or
   section/paragraph, catalog version, and regional specification/version. A
   proposal with any value lacking a `source_ref` (or a reviewer override with
   a reason) **fails validation and cannot be approved**.
4. **Unknown means flagged, not filled.** Missing, ambiguous, or conflicting
   information—including an unknown jurisdiction, currency, language, or
   regional policy—becomes a `NEEDS INPUT` item shown to the salesperson.
   Never use a default, an average, a "typical" value, model knowledge, or a
   value from a different venue, region, season, or policy version.
5. **Numeric-leak guard.** Any LLM-drafted text is scanned for digits,
   currency, percentages, and quantity words. If any appear and do not exactly
   match a value already in the proposal's structured data, the text is
   rejected and regenerated, or replaced with template boilerplate.
6. **Money is `Decimal` plus ISO 4217 currency.** Never use `float` for
   money. Minor-unit precision and rounding happen only at points defined by
   the selected regional rules. Do not assume cents, `ROUND_HALF_UP`, or a
   default currency; all are data-backed regional decisions.
7. **Reproducibility.** Every proposal pins the `region_spec_id`,
   `regional_policy_version`, `catalog_version`, `rules_version`,
   `prompt_version`, `llm_model`, locale, currency, and timezone used to
   generate it. Re-rendering an existing proposal must produce identical
   figures and localized output.
8. **Humans approve, the system never sends.** The system produces drafts and
   exports approved files to the configured approved-artifact location. It
   never emails, shares, or sends anything to a client.

#### Core domain objects

| Object | Key fields (not exhaustive) |
|---|---|
| `RegionalSpecification` | `region_spec_id`, `version`, ISO country/subdivision/locality and jurisdiction IDs, IANA timezone, BCP 47 locale/languages, ISO 4217 currency, formatting rules, effective window, approved catalog/template/policy IDs, `source_ref` |
| `Venue` | `venue_id` (slug), `region_spec_id`, `display_name`, `aliases[]`, location/jurisdiction IDs, `capacity_by_service_style`, `template_id`, `required_fees[]`, `restrictions[]`, `source_ref` |
| `Menu` | `menu_id`, `region_spec_id`, `name`, localized content, `season`/`valid_from`/`valid_to`, `event_types[]`, `service_styles[]`, `venues[]` (or all), `sections[]`, `source_ref` |
| `MenuItem` | `item_id`, `menu_id`, localized `section`/`name`/`description`, region-defined dietary/allergen tags, `price_basis`, `source_ref` |
| `PriceListItem` | `sku`, `region_spec_id`, localized `description`, `unit` (`per_guest`, `per_item`, `per_hour`, `flat`), `unit_price` (`Decimal`), ISO 4217 `currency`, `min_qty`, `valid_from`/`valid_to`, `source_ref` |
| `BusinessRule` | `rule_id`, `region_spec_id`, `description`, `parameters` (from data), `effective_from`/`effective_to`, `source_ref`, implementation function in `rules/` |
| `EventBrief` | `client_name`, `client_contact`, `event_date`, `event_location`, `region_spec_id`, `venue_id`, `guest_count`, `event_type`, `service_style[]`, `preferred_language`, `menu_preferences`, `dietary_requirements`, `other_requirements`, per-field `confidence` and `evidence_span` |
| `Proposal` | `proposal_id`, `status`, `brief`, `regional_specification`, `line_items[]`, `totals`, `warnings[]`, `needs_input[]`, `overrides[]`, pinned versions, `docx_path`, `pdf_path` |
| `CatalogVersion` | `catalog_version` (timestamp ID), source file hashes, validation report, `is_active` |

#### Proposal pipeline

```
Free-text brief (+ optional form fields)
        │
        ▼
[regional]  resolve approved organization/venue/event-location configuration
            → exactly one RegionalSpecification, or NEEDS_CLARIFICATION
        │
        ▼
[intake]    LLM tool call → EventBrief (schema-validated, evidence spans,
            regional specification and language constrained by configuration)
        │   missing/ambiguous required fields → NEEDS_CLARIFICATION
        ▼
[catalog]   resolve venue (exact/alias/fuzzy; ambiguity → ask)
            filter eligible menus by regional specification, venue, event date,
            event type, service style, language, and approved dietary policy
        ▼
[agent]     LLM picks among eligible menu IDs given preferences (validated)
            retrieval: cite regional/venue policies and inclusions relevant to the brief
        ▼
[rules]     deterministic pricing: per-guest, per-item, staffing, rentals,
            venue fees, minimums, service charge, tax, currency precision
            → line items + totals
        ▼
[proposal]  assemble, attach source_refs, run validators
            (provenance, numeric leak, capacity, season, minimums)
        ▼
[render]    fill the approved regional/venue/language DOCX template with
            locale-aware formatting → DOCX; convert → PDF
        ▼
[review]    salesperson reviews, edits with reasons, approves / requests changes
        ▼
[export]    upload approved DOCX/PDF through the configured content-source adapter
```

The "agent" is a **constrained orchestration**: a fixed pipeline with
LLM-backed steps and a fixed, read-only tool set (`resolve_venue`,
`resolve_regional_specification`, `list_eligible_menus`, `get_menu`,
`search_documents`, `get_venue_policies`, `get_regional_policy`,
`request_clarification`). There is no free-form autonomous loop that can
compute prices, choose a region, or write to external systems. Each LLM step
has a maximum iteration count, a timeout, and a deterministic fallback (ask
the user).

#### Proposal lifecycle

```
DRAFT_REQUESTED → BRIEF_EXTRACTED ⇄ NEEDS_CLARIFICATION
               → SOURCES_RESOLVED → PRICED → RENDERED → IN_REVIEW
IN_REVIEW → CHANGES_REQUESTED → (back to SOURCES_RESOLVED or PRICED)
IN_REVIEW → APPROVED → EXPORTED
any non-terminal state → FAILED (with reason) | CANCELLED
```

Only an authenticated reviewer can move a proposal to `APPROVED`, and only
when validation passes with zero unresolved `NEEDS INPUT` items. Every
transition is written to `audit_events` (who, when, from, to, reason).

#### Review UI (v1)

- Shows the extracted brief side by side with the original text, with
  evidence highlights and low-confidence fields marked.
- Shows the selected region, jurisdiction, locale, currency, language, and
  policy version before proposal content; any ambiguity is blocking.
- Shows every line item with quantity, unit price, total, and a **source link**
  (the configured source document plus the sheet/cell or section).
- Lists `NEEDS INPUT` items and warnings first.
- Allows overrides of quantity, price, or inclusion. Each override **requires a
  reason**, is attributed to the signed-in user, and is stored on the proposal
  only. Overrides are never written back to source data.
- Offers DOCX/PDF preview, Approve, Request changes, and Cancel.

#### Ingestion

- Sources: a configured content-source adapter, initially a SharePoint/OneDrive
  library/folder (Graph) or a local folder (development and sanitized sample
  datasets). All adapters must expose a stable source ID, version/etag or
  content hash, and read-only access to approved sources.
- Excel pricing workbooks are parsed with `openpyxl` against a declared sheet
  schema (`data/source_schemas/*.yaml`). Any unexpected header, a non-numeric
  price, an unsupported currency, a duplicate SKU within a region, an
  unrecognized regional specification, or an overlapping validity window is a
  **validation error**.
- Menus and venue documents (DOCX) are parsed with `python-docx` into
  structured records where a structure is declared, and into cited chunks
  otherwise.
- Each ingestion run produces a new `CatalogVersion`. It becomes active
  **only if every affected regional specification validates**; partial
  activation is forbidden. The previous version stays available for
  re-rendering older proposals.
- Source files are **read-only** to this system.

#### Open questions (require maintainer/business confirmation; do not guess)

- Regional onboarding evidence: which authoritative sources define each
  region's tax, food-safety/allergen, language, currency, and service rules.
- Currency minor-unit and rounding policies, including whether service charge
  is taxable, for each supported jurisdiction.
- Conflict precedence when an event venue, client, and service location span
  several jurisdictions.
- The authoritative list of event types and service styles, and how they map
  to menus within each regional specification.
- Whether menus are venue-specific, regional, or shared through explicitly
  approved cross-region mappings.
- The first supported languages, currency/jurisdiction combinations, and
  formatting/translation sources for the global prototype.
- Which of the about 10 completed proposals are representative enough to be
  golden cases (some may contain negotiated one-off pricing).

---

## 2. Assumed Tech Stack (stated explicitly; flag to maintainer before changing)

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.12** | Best ecosystem for LLM SDKs, Office file parsing, and data work; named in the client brief |
| Packaging | **uv** (`pyproject.toml` + `uv.lock`) | Fast, reproducible, single tool for venv/lock/run |
| Web/API | **FastAPI** + **Jinja2 + HTMX** for the reviewer UI | One Python stack, no Node build chain; good enough for an internal review UI |
| Data models | **Pydantic v2** | Schema-constrained LLM outputs and API validation share the same models |
| Database | **PostgreSQL 16 + pgvector** (`pgvector/pgvector:pg16`, pinned digest) | Relational tables for structured catalog data plus vector and full-text search for narrative documents, in one store |
| ORM / migrations | **SQLAlchemy 2.x** + **Alembic** | Mature, typed, explicit migrations |
| Job queue | **Postgres-backed queue** (`procrastinate`) in a `worker` container | Avoids adding Redis for the prototype's low volume |
| LLM | **Anthropic Claude** (default) / **OpenAI** via `llm/` provider interface; model ID pinned in config | The client asked for either; tool calling plus structured output on both |
| Embeddings | Provider embedding model behind the same interface; dimension stored with the index | Swappable without schema surprises |
| Retrieval | Hybrid: PostgreSQL full-text (`tsvector`) + pgvector cosine, merged with reciprocal rank fusion | Exact terms (venue names, SKUs) matter as much as semantics |
| Office parsing | `openpyxl` (Excel), `python-docx` (Word) | Pure Python, no Office install needed |
| Proposal rendering | **`docxtpl`** (Jinja tags inside the venue's own Word template) | Business keeps editing templates in Word |
| PDF conversion | **Gotenberg 8** (LibreOffice) container | Headless, no Word licence on the server; DOCX stays authoritative |
| Content source / identity | Interfaces with local-development adapters plus **Microsoft Graph** via `msal` + `httpx` as the first enterprise source/identity adapter | Keeps regional business logic independent of storage and identity; Graph uses least privilege when configured |
| Logging | `structlog` (JSON) in Python; `Logging.psm1` in PowerShell | Machine-parseable with correlation IDs |
| Quality | `ruff` (lint+format), `mypy --strict` on `src/`, `pytest`, `pytest-recording` (VCR cassettes for LLM/Graph), Pester 5 for PowerShell | Deterministic CI without live API spend |
| Host installer | **PowerShell 5.1+ (7-compatible)** scripts, state-machine driven | Native to Windows; required for DISM, WSL, Scheduled Tasks, DPAPI |
| Containers | **Docker Desktop (WSL2)** + **Docker Compose** | Isolation; the same stack runs on a developer laptop and the office machine |

Rules:

- Do not add LangChain, LlamaIndex, or similar orchestration frameworks
  without sign-off. The pipeline is small and must stay auditable; use the
  provider SDKs directly behind `llm/`.
- Do not introduce Python, Node, or any other runtime on the **host** for the
  installer's own logic. Python runs inside containers. Developer machines
  may use `uv` natively.
- Power Automate, n8n, Make, Teams bots, and email intake are future
  integration points (§16), not v1 dependencies.

---

## 3. Repository Structure

```
Catering_Automation/
├── AGENTS.md
├── README.md
├── JOB DESCRIPTION.txt                 # original client brief (read-only input)
├── .gitignore
├── .env.example                        # every config key, no real values
├── pyproject.toml
├── uv.lock
├── workflows/
│   ├── taskworkflow.md                 # process for non-trivial tasks
│   └── tasks/                          # per-task notes (Git-ignored)
├── docs/
│   ├── architecture.md
│   ├── adr/                            # NNNN-title.md architecture decisions
│   └── user-manual/
│       ├── salesperson.md
│       ├── reviewer.md
│       └── administrator.md
├── src/catering_agent/
│   ├── constants.py                    # §5 constants (Python side)
│   ├── config.py                       # pydantic-settings; reads .env / secrets
│   ├── logging.py                      # structlog setup, redaction processors
│   ├── domain/                         # Pydantic models: EventBrief, Proposal, ...
│   ├── db/
│   │   ├── models.py                   # SQLAlchemy models
│   │   └── migrations/                 # Alembic
│   ├── integrations/                   # source-storage and identity interfaces; Graph adapter
│   ├── knowledge/                      # ingestion, parsers, chunking, embeddings, retrieval
│   ├── catalog/                        # repositories for venues, menus, price lists, versions
│   ├── intake/                         # brief extraction + clarification logic
│   ├── llm/
│   │   ├── providers/                  # anthropic.py, openai.py behind one interface
│   │   ├── prompts/                    # versioned prompt files (e.g. extract_brief.v3.md)
│   │   └── tools.py                    # tool/JSON schemas generated from Pydantic
│   ├── agent/                          # constrained orchestration of the pipeline
│   ├── rules/                          # deterministic pricing & business rules
│   ├── proposal/                       # assembly, validators, provenance, numeric-leak guard
│   ├── render/                         # docxtpl filling, Gotenberg PDF client
│   ├── api/                            # FastAPI app, routes, auth
│   ├── ui/                             # Jinja2 templates + HTMX partials, static assets
│   └── jobs/                           # worker entry point and job definitions
├── data/
│   ├── rules/                          # rule parameters & metadata (YAML), each with source_ref
│   ├── source_schemas/                 # declared sheet/section schemas for ingestion
│   └── samples/                        # SANITIZED prototype dataset (no real client data)
├── evals/
│   ├── golden/                         # golden-NN/{brief.txt, expected.json}
│   ├── extraction/                     # brief → EventBrief fixtures
│   └── run.py                          # python -m evals.run --suite <name>
├── installer/
│   ├── install.ps1                     # state-machine driver, entry point
│   └── scripts/
│       ├── preflight.ps1
│       ├── enable-features.ps1
│       ├── install-docker.ps1
│       ├── collect-config.ps1
│       ├── resolve-existing.ps1
│       ├── provision-containers.ps1
│       ├── sync-sources.ps1
│       ├── ingest-knowledge.ps1
│       ├── run-baseline-eval.ps1
│       ├── configure-backups.ps1
│       ├── configure-compaction.ps1
│       ├── backup.ps1                  # scheduled
│       ├── cleanup-backups.ps1         # scheduled, after backup
│       ├── compact-storage.ps1         # scheduled, consent-gated
│       └── common/
│           ├── Logging.psm1
│           ├── StateManager.psm1
│           ├── Secrets.psm1            # DPAPI-protected secret storage
│           └── Utils.psm1
├── docker/
│   ├── Dockerfile                      # one image for app, worker, migrate
│   ├── docker-compose.yml
│   └── .env.template
└── tests/
    ├── unit/                           # mirrors src/catering_agent/
    ├── integration/                    # DB, Graph (recorded), LLM (recorded), render
    ├── e2e/                            # brief → approved DOCX on sample dataset
    ├── cassettes/                      # recorded HTTP for LLM/Graph (scrubbed)
    └── powershell/
        ├── Preflight.Tests.ps1
        ├── StateManager.Tests.ps1
        └── BackupCleanup.Tests.ps1
```

---

## 4. Build / Test / Run Commands

Development (any OS, from the repository root):

| Purpose | Command |
|---|---|
| Install dependencies | `uv sync` |
| Lint + format check | `uv run ruff check . ; uv run ruff format --check .` |
| Type check | `uv run mypy src` |
| Unit + recorded integration tests | `uv run pytest` |
| A single area | `uv run pytest tests/unit/rules -q` |
| Live LLM / Graph tests (cost money; manual only) | `uv run pytest -m live` |
| Apply DB migrations | `uv run alembic upgrade head` |
| New migration | `uv run alembic revision --autogenerate -m "<summary>"` (review the output; autogenerate is not trusted blindly) |
| Ingest sample dataset | `uv run python -m catering_agent.knowledge.ingest --source local --path data/samples` |
| Golden evaluation | `uv run python -m evals.run --suite golden` |
| Extraction evaluation | `uv run python -m evals.run --suite extraction` |
| Structured-only golden eval (no LLM; installer baseline) | `uv run python -m evals.run --suite golden --mode structured` |
| Run the dev server | `uv run uvicorn catering_agent.api.main:app --reload --host 127.0.0.1 --port 8080` |

Containers:

| Purpose | Command |
|---|---|
| Build and start | `docker compose -f docker/docker-compose.yml up -d --build` |
| Status / health | `docker compose -f docker/docker-compose.yml ps` |
| Logs | `docker compose -f docker/docker-compose.yml logs -f app worker` |
| One-off ingest | `docker compose -f docker/docker-compose.yml run --rm worker python -m catering_agent.knowledge.ingest --source sharepoint` |

Installer (Windows):

| Purpose | Command |
|---|---|
| PowerShell tests | `Invoke-Pester ./tests/powershell` (Pester 5) |
| Full install | `./installer/install.ps1` (elevated) |
| Dry run of one stage | `./installer/scripts/preflight.ps1 -WhatIf` |

Every installer script must be independently runnable, idempotent, and support
`-WhatIf`. **Never test destructive stages (Reset, volume teardown, backup
cleanup) on a machine with real company or client data**; use Windows Sandbox
or a disposable VM.

---

## 5. Global Constants (use these exact values/paths everywhere; do not invent alternates)

```powershell
$AppName          = "CateringProposalAgent"
$AppDataRoot      = "$env:LOCALAPPDATA\$AppName"
$StateFilePath    = "$AppDataRoot\state.json"
$SecretsDirectory = "$AppDataRoot\secrets"            # DPAPI-protected, ACL: installing user only
$LogDirectory     = "$AppDataRoot\logs"
$LogFilePath      = "$LogDirectory\install.log"
$BackupRoot       = "$env:USERPROFILE\CateringProposalAgent-Backups"  # host folder, OUTSIDE Docker volumes
$ComposeProject   = "catering"
$ComposeFile      = "docker\docker-compose.yml"
$DockerNetwork    = "catering_net"
$DbVolumeName     = "catering_db_data"
$DocstoreVolume   = "catering_docstore"                # rendered drafts, synced source copies
$AppPort          = 8080                               # the ONLY published port, bound to 127.0.0.1
```

```python
# src/catering_agent/constants.py
APP_NAME = "CateringProposalAgent"
APP_PORT = 8080
DB_NAME = "catering"
MONEY_QUANTUM = Decimal("0.01")
LLM_TEMPERATURE_EXTRACTION = 0
LLM_MAX_TOOL_ITERATIONS = 6
LLM_REQUEST_TIMEOUT_S = 60
RETRIEVAL_TOP_K = 8
LOW_CONFIDENCE_THRESHOLD = 0.75  # brief fields below this are highlighted for review
SECRET_MASK = "********"
```

Rules:

- **Business values are not constants.** Tax rates, service-charge rates,
  minimums, staffing ratios, venue fees, capacities, prices, currencies,
  timezone, locale, language, regional jurisdiction, and formatting rules
  must never appear in `constants.py`, code, prompts, or templates. They come
  from the selected `RegionalSpecification`, catalog, or `data/rules/`. A unit
  test scans `src/catering_agent/rules/` and `llm/prompts/` for numeric
  literals other than `0`, `1`, and `100` and fails on new ones.
- PostgreSQL (5432) and Gotenberg (3000) ports are **never** published to the
  host. They exist on `catering_net` only. The pre-flight port check therefore
  only checks `$AppPort`.
- Environment-specific values (tenant ID, client ID, SharePoint site URL,
  library and folder names, configured source/identity adapter, LLM provider,
  model ID, and any organization-level regional-specification selector) live
  in `.env` or the state file, not in constants.

---

## 6. Installation State Machine

This is the backbone of the installer. Every stage below **must** write its
completion to `$StateFilePath` before moving to the next one, so a crash,
reboot, or manual close resumes exactly where it left off and never restarts
the whole flow from zero. Implement it in `installer/scripts/common/StateManager.psm1`.

### 6-A. State File Schema

```json
{
  "schema_version": 1,
  "stage": "KNOWLEDGE_INGESTED",
  "app_version": "0.1.0",
  "compose_project": "catering",
  "app_port": 8080,
  "wsl_memory": "6GB",
  "wsl_processors": 2,
  "llm_provider": "anthropic",
  "llm_model": "<pinned model id>",
  "source_adapter": "m365_graph",
  "identity_adapter": "m365_entra",
  "configured_region_specs": [
    {
      "region_spec_id": "example-region",
      "version": "2026-10-11",
      "country_code": "<ISO 3166-1 alpha-2>",
      "timezone": "<IANA timezone>",
      "locale": "<BCP 47 language tag>",
      "currency": "<ISO 4217 code>"
    }
  ],
  "m365": {
    "tenant_id": "00000000-0000-0000-0000-000000000000",
    "client_id": "00000000-0000-0000-0000-000000000000",
    "sharepoint_site_url": "https://contoso.sharepoint.com/sites/Sales",
    "source_library": "Proposal Sources",
    "drafts_folder": "Proposals/Drafts",
    "approved_folder": "Proposals/Approved"
  },
  "reviewer_allowlist": ["sales.lead@contoso.com"],
  "active_catalog_version": "2026-10-11T20:15:00Z",
  "last_error": null,
  "last_updated": "ISO-8601 timestamp"
}
```

**Secrets are never stored in the state file.** The LLM API key, credentials
for the selected source/identity adapters (including a Graph client secret
when selected), and generated PostgreSQL password are stored in
`$SecretsDirectory` via `Secrets.psm1`, which uses `ConvertFrom-SecureString`
(DPAPI, current user). They are materialized as Docker Compose `secrets:`
files only at `compose up` time, with ACLs restricted to the installing user
(see §17).

### 6-B. Stage Enum

Implement as a PowerShell enum or ordered constant list in `StateManager.psm1`:

```
NOT_STARTED
PREFLIGHT_DONE
FEATURES_ENABLED_PENDING_RESTART
FEATURES_CONFIRMED
DOCKER_READY
CONFIG_COLLECTED
EXISTING_INSTALL_RESOLVED
CONTAINERS_PROVISIONED
DB_HEALTHY
MIGRATIONS_APPLIED
SOURCES_SYNCED
KNOWLEDGE_INGESTED
BASELINE_EVAL_PASSED
BACKUP_CONFIGURED
COMPACTION_SCHEDULED
COMPLETE
```

### 6-C. Flow Details

**Stage: PREFLIGHT_DONE**
Run `preflight.ps1` (see §7). Hard blockers abort with a clear,
plain-English message. Raw PowerShell errors are logged, never shown; the
user sees a friendly summary and the log path. Soft warnings are shown but do
not block.

**Stage: FEATURES_ENABLED_PENDING_RESTART → FEATURES_CONFIRMED**
See §8. **Never call `Restart-Computer` automatically.** Always show a dialog
with "Restart Now" / "Restart Later", both user-initiated. Register a
Scheduled Task (`Register-ScheduledTask`, trigger `AtLogOn`) that relaunches
`install.ps1`. On relaunch it reads the state file and advances to
`FEATURES_CONFIRMED` only after `wsl --status` succeeds. Remove the task once
the stage is confirmed.

**Stage: DOCKER_READY**
Detect Docker Desktop via `Get-Command docker -ErrorAction SilentlyContinue`
plus `docker version`. If it is absent, install it silently using the official
installer. If it is present but outdated, **warn and let the user choose** to
upgrade; never auto-upgrade, because other projects may depend on the current
version. Confirm the WSL2 backend is active and the engine responds.

**Stage: CONFIG_COLLECTED**
Collect the values in §9.1 via wizard prompts. Validate each field, then
**verify connectivity before accepting it**: validate every selected
source/identity adapter (for Graph, acquire a token and list the source
library), validate the initial regional specification configuration, and make
a minimal LLM API call (a one-token completion) to confirm the key and model
ID. Store non-secrets in the state file and secrets via `Secrets.psm1`. Write
the WSL resource values to
`%USERPROFILE%\.wslconfig` under `[wsl2]`.

**Stage: EXISTING_INSTALL_RESOLVED**
Check for existing containers in compose project `$ComposeProject`, the
volumes `$DbVolumeName` / `$DocstoreVolume`, or the network `$DockerNetwork`.
If any are found, present exactly these four choices and never auto-wipe:

- **Resume**: continue an interrupted install using the existing state.
- **Repair**: rebuild images and containers and re-run migrations without
  touching volumes.
- **Reset**: destroy and recreate containers and volumes. Requires typed
  confirmation (the user must type `RESET CATERING`). Before destroying
  anything, run `backup.ps1` and verify a complete backup set exists. Reset
  **never** deletes `$BackupRoot`, `$SecretsDirectory`, or anything in
  SharePoint.
- **Cancel**

**Stage: CONTAINERS_PROVISIONED**
Run `docker compose -p $ComposeProject -f $ComposeFile up -d --build`. See §11.

**Stage: DB_HEALTHY**
Do not proceed until the `db` healthcheck reports healthy (see §12). Poll
`docker inspect --format '{{.State.Health.Status}}'` with a bounded total
timeout. **Never use a fixed `Start-Sleep` as a substitute.**

**Stage: MIGRATIONS_APPLIED**
Confirm the one-shot `migrate` service exited `0` and that
`alembic current` equals `alembic heads`. Then confirm `GET /readyz` on the
app returns `200`.

**Stage: SOURCES_SYNCED**
Run `sync-sources.ps1`, which runs
`docker compose run --rm worker python -m catering_agent.integrations.sync`.
That command downloads the configured approved sources to the docstore volume,
recording provider IDs, versions/eTags, and content hashes. It is read-only
against approved source libraries. A Graph `401`/`403` is a hard stop with
instructions for the tenant admin to grant `Sites.Selected` (see §10).

**Stage: KNOWLEDGE_INGESTED**
Run `ingest-knowledge.ps1`, which runs the ingest job against the synced
sources. Any validation error stops the stage and produces a readable report
(file, sheet, cell, problem) for the content owner. Nothing is activated. On
success, record the `active_catalog_version` in the state file.

**Stage: BASELINE_EVAL_PASSED**
Run `run-baseline-eval.ps1`, which runs
`python -m evals.run --suite golden --mode structured`. This mode feeds
pre-extracted structured briefs to the rules engine with no LLM cost, which
proves the ingested data and rules reproduce the golden proposals' line items
and totals. A failure blocks completion and lists the mismatching cases. It
usually means the source data changed or ingestion mis-parsed a sheet.

**Stage: BACKUP_CONFIGURED**
See §13.

**Stage: COMPACTION_SCHEDULED**
See §14.

**Stage: COMPLETE**
Open the default browser at `http://127.0.0.1:$AppPort`. Create a desktop
shortcut and a Start/Stop shortcut (`docker compose start|stop`). Write a
final success entry to the log, including the versions of every component.

---

## 7. Pre-flight Checks

| Check | PowerShell approach | Type |
|---|---|---|
| Windows version | `[System.Environment]::OSVersion.Version` ≥ `10.0.19041` | Hard blocker |
| Admin privileges | `([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)` | Hard blocker |
| PowerShell version | `$PSVersionTable.PSVersion` ≥ 5.1 | Hard blocker |
| Virtualization enabled | `(Get-CimInstance Win32_ComputerSystem).HypervisorPresent`, or firmware virtualization via `Get-CimInstance Win32_Processor` | Hard blocker |
| WSL/VM Platform blocked by Group Policy | Catch the specific policy error from `Enable-WindowsOptionalFeature`; distinguish policy restriction from generic failure | Hard blocker |
| Free disk space | `(Get-PSDrive C).Free`: 40 GB recommended, **20 GB hard minimum** | Hard blocker below 20 GB; soft warning below 40 GB |
| RAM | `(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory`: warn below 8 GB; 16 GB recommended | Soft warning |
| Internet: Docker Hub | HTTPS `GET https://registry-1.docker.io/v2/` (expect `401`, which proves reachability) | Hard blocker |
| Internet: configured source/identity adapters | HTTPS reachability for each selected network adapter; for the Graph adapter, test `https://login.microsoftonline.com` and `https://graph.microsoft.com` | Hard blocker for the selected adapter |
| Internet: LLM provider | HTTPS reachability of `https://api.anthropic.com` or `https://api.openai.com` (whichever is configured) | Hard blocker |
| System clock | Compare local UTC with an HTTP `Date` header from the configured source/identity endpoint; Graph is used when the Graph adapter is selected. Warn if skew is over 2 minutes | Soft warning |
| Port availability | `Get-NetTCPConnection -LocalPort $AppPort -State Listen -ErrorAction SilentlyContinue`; only `$AppPort` (see §5) | Soft warning; offer to stop or pick another port and record it in state |
| Windows Firewall status | `Get-NetFirewallProfile`: report only; no inbound rule is needed because the app binds to `127.0.0.1` | Soft warning |
| Existing Docker Desktop | `docker version --format '{{.Server.Version}}'` | Soft warning |
| Corporate proxy | **Not implemented in v1.** Do not add proxy detection; a future request is a new feature, not a bug fix | Out of scope |

---

## 8. Windows Feature Enablement

```powershell
$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
$vmpFeature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform

if ($wslFeature.State -ne 'Enabled' -or $vmpFeature.State -ne 'Enabled') {
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
    # Always -NoRestart: the installer decides when the user is asked, never Windows.
    Set-InstallState -Stage "FEATURES_ENABLED_PENDING_RESTART"
    Register-ResumeTask          # AtLogOn scheduled task relaunching install.ps1
    Show-RestartPrompt           # Restart Now / Restart Later, both user-driven
    return
}

wsl --update                     # ensure the WSL kernel is current
wsl --set-default-version 2
```

On relaunch after a restart, verify with `wsl --status` (exit code `0`) before
advancing the stage. Never assume success just because a reboot happened.

---

## 9. User Input Field Rules

### 9.1 Installer configuration fields

| Field | Rules |
|---|---|
| Microsoft Entra tenant ID | GUID format; verified by acquiring a token |
| App registration client ID | GUID format |
| App registration client secret | Masked input with a confirm field; stored only via `Secrets.psm1`; never logged (`********`); certificate credentials are a future option |
| SharePoint site URL | Must match `^https://[a-z0-9-]+\.sharepoint\.com/sites/[^/]+/?$`; verified by resolving the site via Graph |
| Source library / drafts folder / approved folder | Non-empty; must exist (source) or be creatable (drafts/approved); drafts and approved must not be inside the source library |
| Source and identity adapters | Select supported adapters. Local source is for development only; Graph/Entra is the initial enterprise adapter. Each adapter is independently verified and must expose source/version provenance and least-privilege access. |
| Initial regional specifications | One or more approved, versioned specifications. Validate ISO country/subdivision identifiers, IANA timezone, BCP 47 locale, ISO 4217 currency, effective dates, regional templates/catalogs/rules, and source references. No region is enabled without an approved policy pack. |
| LLM provider | Radio: `anthropic` or `openai` |
| LLM API key | Masked with a confirm field; verified by a minimal call; stored only via `Secrets.psm1`; never logged |
| LLM model ID | Pre-filled with the pinned default for the chosen provider; free text allowed; verified by the minimal call. Changing it later requires a golden eval (§18) |
| Reviewer allowlist | One or more email addresses (UPNs) allowed to approve; validated email format |
| WSL2 resources | Defaults `memory=6GB`, `processors=2`; editable; written to `%USERPROFILE%\.wslconfig` `[wsl2]`. Do not set any disk-size key, because no such `.wslconfig` setting exists (see §14) |
| PostgreSQL password | **Generated**, never typed: 32 random characters via `System.Security.Cryptography.RandomNumberGenerator`; stored only via `Secrets.psm1` |

### 9.2 Event brief fields (reviewer UI and intake)

The salesperson may type a free-text brief, fill the form, or both. The form
always shows the extracted values for confirmation. **Required fields are never
inferred from defaults**; if a field is missing or ambiguous, the system asks.

| Field | Required | Rules |
|---|---|---|
| Client name | Yes | Free text, 1–200 chars; treated as PII (§10, §15) |
| Client contact (email/phone) | No | Validated format if present; PII |
| Event location / regional specification | Yes | Must resolve to exactly one approved `region_spec_id` using configured organization/venue/event-location mappings. The client locale, prose, IP address, or model knowledge cannot choose it. Multiple/no matches → `NEEDS INPUT`. |
| Event date | Yes | A single date in the selected regional specification's IANA timezone; must be today or later. An incomplete date (for example, a month without day/year) → `NEEDS INPUT`; no culturally specific date format is assumed. |
| Venue | Yes | Must resolve to exactly one region-scoped `venue_id` by exact name, alias, or configured fuzzy threshold. Multiple candidates → ask; no candidate → `NEEDS INPUT` ("venue not in regional catalog"). Never fall back to a "similar" venue |
| Guest count | Yes | Positive integer; ranges like "140–160" → ask for the planning number; must be within the venue's capacity for the chosen service style (from catalog), otherwise a blocking warning |
| Event type | Yes | Must be one of the event types defined in the catalog (e.g. wedding, corporate); unknown → ask |
| Service style | Yes | One or more catalog service styles (e.g. cocktail reception, seated dinner, buffet); order matters (sequence of service) |
| Proposal language | Yes | Must be one of the document languages approved by the selected regional specification. Missing, unsupported, or conflicting language → `NEEDS INPUT`; translations come only from approved localized catalog/template content. |
| Menu preferences | No | Free text; used only to rank eligible menus; never creates menu items |
| Dietary requirements | No | Free text plus structured counts if given ("12 vegetarian"); counts must be ≤ guest count |
| Other requirements | No | Free text (rentals, bar, staffing requests); items that map to catalog SKUs are priced; unmapped items become `NEEDS INPUT`, never a guessed price |

Every extracted field stores an `evidence_span` (the exact substring of the
  brief it came from) and a `confidence`. Fields without evidence that were not
typed into the form are treated as missing. The confirmed regional
specification, locale, timezone, language, and currency are copied into the
proposal's immutable generation context.

---

## 10. Security Checklist (verify all of these before marking a build release-ready)

- [ ] PostgreSQL and Gotenberg have no `ports:` mapping in docker-compose;
      they are on the internal network only.
- [ ] `app` publishes only `127.0.0.1:${APP_PORT}:8080`, not `0.0.0.0`.
- [ ] No secrets in the repo, state file, logs, task notes, test cassettes, or
      Docker images. Cassettes are scrubbed of `Authorization`, `x-api-key`,
      and token fields by a recording filter, and a test fails if a cassette
      contains any of them.
- [ ] Secrets stored via DPAPI (`Secrets.psm1`); Compose secret files and
      `$SecretsDirectory` ACL-restricted to the installing user.
- [ ] Every source and identity adapter uses least privilege and is scoped to
      the configured organization/region only. For the Graph adapter, use
      **`Sites.Selected`** on the approved site (read source library; write
      only drafts/approved folders), not `Sites.Read.All` or
      `Files.ReadWrite.All`.
- [ ] Reviewer identity is provided by the configured identity adapter; only
      identities on the configured reviewer allowlist can approve. Entra is
      the initial adapter and uses delegated `User.Read`. All routes except
      `/healthz` require authentication.
- [ ] Session cookies are `HttpOnly` and `SameSite=Lax`; state-changing
      requests carry CSRF protection.
- [ ] **Prompt-injection containment:** retrieved document text and the user's
      brief are passed to the LLM as clearly delimited data, never as
      instructions. LLM tools are read-only and allowlisted, and there is no
      tool that writes to Microsoft 365, sends messages, or changes prices.
      Every tool argument is validated with Pydantic.
- [ ] LLM output is never executed, `eval`'d, or rendered as raw HTML (Jinja
      autoescape on).
- [ ] The LLM provider is used under API terms that exclude training on
      customer data. Only the minimum client PII needed for the step is sent.
      Extraction needs the brief; pricing steps send none. The configured
      region's data-residency, cross-border transfer, retention, and
      disclosure requirements are recorded and verified before enabling it.
- [ ] Rendered proposals and backups contain client PII: `$BackupRoot` and the
      docstore volume are restricted to the installing user.
- [ ] Containers run as a non-root user (`USER app` in the Dockerfile) where
      the base image supports it.
- [ ] Dependencies pinned via `uv.lock`; container images pinned by digest.
- [ ] Approval, override, and export actions are recorded in
      `audit_events` with user, timestamp, and reason. The table is
      append-only, enforced by a DB role without `UPDATE`/`DELETE` on that
      table.
- [ ] Source documents are never modified by the system. No source adapter
      has a code path that writes to an approved source library.

---

## 11. Docker Compose Requirements

One compose file, `docker/docker-compose.yml`, project name `catering`:

| Service | Role | Notes |
|---|---|---|
| `db` | PostgreSQL 16 + pgvector | Volume `catering_db_data`; no published port; healthcheck in §12 |
| `migrate` | One-shot `alembic upgrade head` | Same image as `app`; `depends_on: db: condition: service_healthy`; `restart: "no"` |
| `app` | FastAPI API + reviewer UI | **Only** service with a published port: `127.0.0.1:${APP_PORT}:8080`; `depends_on: migrate: condition: service_completed_successfully`, `docconv: condition: service_healthy` |
| `worker` | Ingestion, generation, rendering, and export jobs (procrastinate) | Same image; same `depends_on` as `app`; mounts `catering_docstore` |
| `docconv` | Gotenberg 8 (DOCX → PDF) | No published port; healthcheck `GET /health` |

Requirements:

- Network `catering_net` (bridge). All inter-service traffic stays on it.
- Secrets (`db_password`, `llm_api_key`, and any selected adapter credential
  such as `graph_client_secret`) are provided via Compose `secrets:` and read
  from `/run/secrets/*` by `config.py`, not via plain environment variables.
- `app` and `worker` mount `catering_docstore` at `/data/docstore`.
  `$BackupRoot` is bind-mounted read-write **only** into a backup helper
  invocation (§13), never permanently into `app`.
- `restart: unless-stopped` for `db`, `app`, `worker`, and `docconv`.
- All images pinned (tag plus digest). No `latest`.
- `app` exposes `GET /healthz` (process alive) and `GET /readyz` (DB
  reachable, migrations at head, pgvector extension present, Gotenberg
  reachable, an active catalog version exists, secrets loaded). The compose
  healthcheck for `app` uses `/readyz`.

---

## 12. Database Health Checks

```yaml
db:
  image: pgvector/pgvector:pg16@sha256:<pinned-digest>
  environment:
    POSTGRES_DB: catering
    POSTGRES_USER: catering
    POSTGRES_PASSWORD_FILE: /run/secrets/db_password
  secrets: [db_password]
  volumes:
    - catering_db_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U catering -d catering -h 127.0.0.1"]
    interval: 5s
    timeout: 5s
    retries: 24
    start_period: 10s

migrate:
  depends_on:
    db:
      condition: service_healthy

app:
  depends_on:
    migrate:
      condition: service_completed_successfully
    docconv:
      condition: service_healthy
```

Rules:

- `pg_isready` alone proves the server accepts connections, not that the
  schema is ready. That is why `migrate` is a separate gate, and why `/readyz`
  re-checks `alembic current == heads`.
- The first migration runs `CREATE EXTENSION IF NOT EXISTS vector;`.
  `/readyz` fails if the extension is missing.
- Application DB connections use `pool_pre_ping=True` and retry the first
  connection with bounded exponential backoff (max 30 s total), so they
  recover from a DB restart without a crash loop.
- **Never** replace these with `Start-Sleep`, `time.sleep`, or fixed-delay
  workarounds in scripts or code. Startup ordering is solved at the compose
  and readiness level and must stay there.

---

## 13. Backup Implementation

What is backed up (one **backup set** per run, sharing a timestamp prefix
`yyyyMMdd-HHmmss`):

| File | Produced by |
|---|---|
| `<ts>-db.dump` | `docker compose exec -T db pg_dump -U catering -d catering -Fc` streamed to the host |
| `<ts>-docstore.tar.gz` | `docker compose run --rm -v "$BackupRoot:/backup" worker tar -czf /backup/<ts>-docstore.tar.gz -C /data/docstore .` |
| `<ts>-manifest.json` | `backup.ps1`: app version, Alembic head, active catalog version, file sizes, and SHA-256 of each file. **Written last**; its presence marks the set complete |

Rules:

- **Schedule:** every 24 hours via a Windows Scheduled Task running
  `backup.ps1`, plus on demand before any Reset (§6-C) and before any
  migration that alters existing tables.
- **Location:** `$BackupRoot` on the host, outside `$DbVolumeName` and
  `$DocstoreVolume`, so a Reset never destroys backups. Folder ACL restricted
  to the installing user (backups contain client PII).
- **Verification:** after writing, run `pg_restore --list` against the dump
  inside the `db` container. A set that fails verification is renamed with a
  `.failed` suffix and logged as an error. It never counts as the "latest
  good" set.
- **Cleanup** (`cleanup-backups.ps1`, run after each successful backup):
  1. Group files in `$BackupRoot` by timestamp prefix into sets.
  2. Treat a set as complete only if its manifest exists, every file listed in
     it exists with a matching SHA-256, and no file in it was modified in the
     last 10 minutes or is locked. Skip incomplete or in-progress sets; never
     delete them in the same run.
  3. Delete complete sets older than 360 hours (15 days).
  4. **Always retain at least the single most recent complete, verified set,
     regardless of age.** This is a hard safety floor.
- **Restore** (documented in `docs/user-manual/administrator.md` and tested
  per §18): stop `app` and `worker`, then `pg_restore --clean --if-exists`,
  untar the docstore, start the services, and confirm `/readyz`.
- Approved proposals are also exported to the configured approved-artifact
  location (the SharePoint `Approved` folder when the Graph adapter is used),
  which is the business system of record for finished proposals. Local backups
  protect drafts, audit history, and catalog versions.

---

## 14. Storage and Compaction Implementation

- Pre-flight requires 20 GB free (40 GB recommended) as the baseline. Do not
  implement an artificial cap on database or volume growth.
- Expected growth is small: catalog data plus embeddings for the prototype
  are in the low hundreds of MB, and rendered DOCX/PDF drafts are about
  100 KB to 2 MB each. The WSL2 VHDX still only ever grows, so compaction is
  needed over time.
- **Do not enable WSL2's experimental `sparseVhd` setting.** Microsoft flags
  it as experimental with potential corruption risk for always-on database
  workloads. This is a deliberate decision, not an oversight.
- **Disk-usage monitor** (inside `backup.ps1`): warn the user (toast plus a
  log entry) when `$BackupRoot` plus the Docker Desktop VHDX combined usage
  crosses about 80% of the pre-flight baseline, or when free space on the
  drive drops below 10 GB.
- **Monthly compaction** (`compact-storage.ps1`, monthly Scheduled Task):

  ```powershell
  # Only after explicit user consent in a dialog:
  # "Monthly storage optimization is ready — Run Now / Skip this month"
  docker compose -p catering stop
  wsl --shutdown
  Optimize-VHD -Path <docker-desktop-data.vhdx> -Mode Full   # requires Hyper-V module
  # if Hyper-V module is unavailable (Windows Home): fall back to diskpart "compact vdisk"
  ```

  This task **must always prompt the user first**. It is never silent or fully
  automatic, even though it is scheduled. It must also refuse to run while a
  proposal job is in progress (worker queue not empty).
- PostgreSQL maintenance relies on **autovacuum**. Do not schedule
  `VACUUM FULL` (it takes exclusive locks and temporarily needs extra disk).
- Superseded catalog versions and cancelled drafts are **not** auto-deleted
  in v1 (see §17).

---

## 15. Logging Conventions

**Python (`src/catering_agent/logging.py`, structlog, JSON lines):**

- Required fields: `ts` (ISO-8601 UTC), `level`, `event`, `component`
  (e.g. `intake`, `rules`, `render`), `request_id`, and `proposal_id` /
  `job_id` when applicable.
- LLM calls log `provider`, `model`, `prompt_version`, `input_tokens`,
  `output_tokens`, `latency_ms`, `tool_calls`, and `outcome`. They do **not**
  log prompt or response bodies by default. A debug trace mode may store them
  in the access-controlled `llm_traces` table (never in log files), with
  retention noted in §17.
- Rule evaluation logs `rule_id`, `rules_version`, and inputs/outputs by
  reference (line-item IDs), not client details.
- A redaction processor masks secrets (`********`) and PII fields
  (`client_name`, `client_contact`, email addresses, phone numbers). It is
  applied globally; do not bypass it with `print()` or raw `logging` calls.
- Output: stdout in containers (collected by Docker). Do not write log files
  inside containers.

**PowerShell installer (`common/Logging.psm1`):**

- All scripts import `Logging.psm1` and use a single
  `Write-InstallLog -Level <Info|Warning|Error> -Message <string>`. Do not
  use raw `Write-Host` for anything user-facing or diagnostic.
- Format: `[ISO-8601 timestamp] [LEVEL] [stage-name] message`
- File: `$LogFilePath`, append mode, no rotation for v1.
- Never log the LLM API key, adapter credentials (including Graph client
  secrets), DB password, tokens, regional policy contents, or any client
  data. If a value must be referenced, mask it as `********`.

**Audit trail ≠ logs.** Business events (brief submitted, override,
approval, export) go to the `audit_events` table, which is the record of
who did what. Logs are for diagnostics.

---

## 16. Out of Scope — Do Not Implement Without Explicit Sign-Off

- Sending proposals to clients by any channel (email, Teams, share links).
  The salesperson sends them manually.
- CRM integration, contracts, e-signature, invoicing, deposits, or payments.
- Email, Teams-bot, Power Automate, n8n, or Make intake/triggers. Keep a clean
  service boundary (`POST /api/proposals`) so they can be added later.
- Writing back to source documents (pricing workbooks, menus, templates) or
  any "edit pricing from the UI" feature.
- Ingesting the full venue/menu library beyond the prototype dataset (3
  venues, about 5 menus, about 10 golden proposals) until the prototype is
  accepted.
- LAN, remote, or internet exposure of the reviewer UI, and HTTPS. v1 binds
  to `127.0.0.1` over plain HTTP. LAN access requires HTTPS plus a firewall
  review first.
- Cloud deployment (Azure Container Apps, App Service, etc.).
- Fine-tuning or training models on company data.
- Enabling a country, subdivision, language, currency, or jurisdiction without
  an approved `RegionalSpecification`, regional source data, templates, policy
  pack, and the test coverage required by §18.
- Automatic menu creation or "suggest a new dish" features.
- Corporate proxy/VPN passthrough.
- Offsite/cloud backup upload.
- Code signing of installer scripts. Recommended before rollout beyond the
  client's own machine; flag it to the maintainer then.

---

## 17. Known Accepted Risks (do not "fix" silently — these were deliberate trade-offs)

- **LLM extraction can misread a brief.** Mitigation: evidence spans,
  confidence highlighting, mandatory reviewer confirmation of the brief, and
  the extraction eval. The residual risk is accepted because a human approves
  every proposal.
- **Source data accuracy is the business's responsibility.** Ingestion
  validates structure and consistency (types, duplicates, overlapping
  validity), not whether a price is commercially correct.
- **Client PII is sent to the LLM provider** for brief extraction, under API
  terms that exclude training. Accepted for v1; a self-hosted model is a
  future option.
- **Docker Compose secret files exist in plaintext on disk** while the stack
  runs, protected only by user-scoped ACLs. Accepted for a single-user office
  machine.
- **Single machine, backups on the same disk.** A hardware failure can lose
  both live data and local backups. Approved proposals survive in the
  configured approved-artifact location; offsite backup is deferred (§16).
- **PDF fidelity:** LibreOffice may render some Word layouts slightly
  differently. The DOCX is the authoritative artifact, and PDF is a
  convenience copy.
- **Docker Desktop licensing:** free use requires the company to stay under
  250 employees and $10M revenue. Otherwise a paid subscription is the
  customer's responsibility; this codebase does not detect or enforce it.
- **No proxy support:** installs fail on networks that enforce one. This is a
  known v1 limitation, not a bug.
- **Plain HTTP on localhost** is accepted for v1 (§16).
- **No automatic retention** of superseded catalog versions, cancelled drafts,
  or debug `llm_traces`. Storage growth is small; revisit before production.
- **LLM non-determinism** in narrative text and menu ranking. Mitigated by
  temperature 0 for extraction, validated outputs, and the numeric-leak
  guard. Business figures are deterministic by construction.
- **Regional-policy completeness is the customer's responsibility.** The
  system validates that a regional specification has the declared approved
  sources and scope; it cannot certify that every local legal, dietary, tax,
  language, or cultural requirement has been supplied. A missing or
  conflicting policy must block or flag the proposal, never be inferred.

---

## 18. Testing Requirements for Any PR

General (every PR):

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`,
  and `uv run pytest` all pass. Default test runs make **no live network
  calls**: LLM and Graph traffic replays from scrubbed cassettes, and the DB
  uses a disposable PostgreSQL (testcontainers or the compose `db`).
- New behavior includes tests at the lowest level that can prove it, filed
  under the matching suite (`TS-*` IDs in `workflows/taskworkflow.md` §6).
- Never weaken, skip, or re-record a failing test or golden expectation just
  to go green (see the workflow §5).

Accuracy-sensitive changes (`rules/`, `catalog/`, `intake/`, `proposal/`,
`render/`, `llm/prompts/`, `data/rules/`, `data/source_schemas/`, model ID):

- **Golden eval must pass** (`python -m evals.run --suite golden`), and the PR
  description includes its summary. Release thresholds:
  - priced line items and totals: **100% exact match** with each golden
    case's expected output;
  - provenance coverage: **100%** of proposal values have a `source_ref` or
    an override;
  - unsourced menu items or figures: **0**;
  - numeric-leak guard violations in final output: **0**;
  - "never guess" cases (missing date, unknown venue, ambiguous guest count)
    produce `NEEDS INPUT`: **100%**.
- Extraction eval (`--suite extraction`) must not regress on required-field
  accuracy compared with the last recorded baseline in `evals/baselines/`.
- Prompt changes bump the prompt file version (`*.vN.md`). Model ID changes
  require a live run of both eval suites, with results recorded.
- Rule changes add table-driven unit tests whose expected values are
  calculated by hand and cross-checked against at least one golden case or
  source document. Include boundaries: venue min/max capacity, minimum spend
  thresholds, season start/end dates, zero optional items.
- Rendering changes: a test opens every rendered DOCX and asserts no
  unrendered `{{`/`{%` tags remain, every line item appears, and totals in the
  document equal the structured totals.
- Regional-specification changes add `TS-REGION` cases covering: exact
  specification selection, no cross-region catalog leakage, jurisdiction and
  effective-date boundaries, ISO 4217 precision/formatting, IANA-timezone
  date boundaries, BCP 47 language/template selection, and the fail-closed
  result for an unsupported or ambiguous region. Golden cases are region
  scoped and run under their pinned regional specification; a passing case in
  one region is not evidence for another.

Installer and operations changes:

- Any change to `preflight.ps1`, `enable-features.ps1`, or the state machine
  must be tested in Windows Sandbox or a disposable VM snapshot, never on a
  machine with a real install.
- Explicitly test the Resume / Repair / Reset / Cancel branches whenever
  `EXISTING_INSTALL_RESOLVED` logic changes. Confirm Reset takes a verified
  backup first and never touches `$BackupRoot`, `$SecretsDirectory`, or
  SharePoint.
- Test `cleanup-backups.ps1` against a directory containing a deliberately
  incomplete or in-progress set (missing manifest, hash mismatch, recently
  modified file) and confirm it is skipped, not deleted. Also confirm the
  most recent complete set survives even when it is older than 15 days.
- Confirm the `db` healthcheck and `migrate` gate actually block `app`
  startup, by testing against a deliberately slow-starting PostgreSQL and a
  deliberately failing migration.
- Test a backup → Reset → restore round trip on the sample dataset and
  confirm a previously approved proposal re-renders with identical figures.
- `Invoke-Pester ./tests/powershell` passes, and secret-masking tests confirm
  no secret value appears in `$LogFilePath`.
