# Task Workflow — Catering Proposal AI Agent

Use this process for every non-trivial task in this repository. Its purpose is
to preserve understanding, decisions, progress, and verification across long
sessions, interruptions, and context compaction without reducing the coding
agent's normal ability to proceed autonomously.

This workflow sits underneath `AGENTS.md`. `AGENTS.md` defines *what* the
system must do and the hard rules it must obey; this file defines *how* a task
is carried from request to verified completion.

The core product rule shapes every step below: **the system must never guess
pricing, menu items, venue requirements, regional requirements, or any other
business fact.** Any task that touches extraction, retrieval, rules, pricing,
menus, templates, regional specifications, translations, or prompts is
*accuracy-sensitive* and carries extra verification obligations (see §0 and
§5).

---

## 0. Classify and Set Up

Classify the task before doing anything else.

| Class | Examples | Task workspace? |
|---|---|---|
| **Trivial** | One-line fix, typo, simple read-only answer, rename with obvious verification | No |
| **Standard** | New endpoint, parser change, UI screen, installer stage, refactor across files | Yes |
| **Accuracy-sensitive** | Anything under `src/catering_agent/rules/`, `catalog/`, `intake/`, `proposal/`, `render/`, `llm/prompts/`, `data/rules/`, `evals/golden/`, or any change to how a price, menu item, venue fact, regional policy, locale, or quantity reaches a proposal | Yes, and the golden evaluation is mandatory (§5) |
| **Customer-facing / deployment** | Dedicated-client hosting, remote access, authentication boundaries, the Catering Enquiry Assistant, public forms, or PWA/mobile delivery | Yes, and security/privacy validation is mandatory |
| **Destructive / environment** | Installer Reset path, data migrations, backup cleanup, compaction, deleting catalog versions | Yes, and must follow the disposable-VM rules in `AGENTS.md` §18 |

When a task needs a workspace, derive a short kebab-case slug (for example
`venue-alias-matching`, `service-charge-rule`) and create:

```text
workflows/tasks/<slug>/
```

`workflows/tasks/` is Git-ignored. Create files only when their phase begins:

- `00-brief.md`: the requested outcome restated in your own words, plus scope,
  constraints, assumptions, acceptance criteria, and explicitly excluded work.
- `01-research.md`: files inspected, relevant paths, existing patterns,
  external facts checked (with source), current Git state, and findings.
- `02-plan.md`: a phased checklist with a verifiable result for each phase.
- `03-progress.md`: a dated record of completed phases, edits, commands, test
  results, and remaining work.
- `04-decisions.md`: consequential choices, the alternatives considered,
  rationale, open questions, and blockers.
- `05-validation.md`: the final comparison with the brief. It covers commands
  and checks run, golden-eval results, limitations, and any manual validation
  still required.
- `06-test-cases.md`: requirement-linked test cases organized into test suites
  (see §6).
- `07-user-manual.md`: a draft of user-facing instructions when the task
  changes how salespeople, reviewers, or the installing administrator operate
  the product (see §7).
- `scratch.md`: temporary notes, experiments, discarded approaches, and command
  fragments. It is never authoritative.

Task notes must **never** contain:

- passwords, API keys, client secrets, tokens, or private keys;
- real client names, contact details, event details, or completed-proposal
  content (use the sanitized fixtures in `data/samples/` and refer to golden
  cases by ID, e.g. `golden-07`); or
- full LLM prompts or responses that contain client data.

---

## 0-A. Brief Requirements

Record in `00-brief.md`:

- the user-visible problem, the expected result, and how that result will be
  validated;
- the authorized scope and the files, services, or data likely to be affected;
- assumptions that are safe and reversible, marked as assumptions;
- acceptance examples and failure/boundary cases supplied by the user (for
  example: "150-person wedding at the Brazilian Room in September → venue
  resolves to `brazilian-room`, autumn menus offered, guest count within venue
  capacity");
- whether the task is **accuracy-sensitive**, and if so which proposal outputs
  it can change (line items, quantities, totals, menu text, venue facts,
  narrative text);
- the regional impact: which `RegionalSpecification` fields, jurisdictions,
  currencies, languages, tax rules, dietary/allergen rules, date/number
  formats, or country-specific templates can change, and which regions must
  remain unaffected;
- whether data, compatibility, security, Microsoft 365 permissions, LLM
  provider behavior, installation, or destructive actions are involved;
- for delivery-channel work, whether the change affects the dedicated-client
  isolation boundary, a public/customer route, authentication/authorization,
  HTTPS, consent/PII handling, rate limiting, abuse prevention, or backups;
- whether the work belongs to the internal proposal portal or the future
  Catering Enquiry Assistant, and which actions the user must never be able
  to invoke; and
- which catalog version, prompt version, or golden cases the change is
  expected to affect, and which it must not affect; and
- relevant pre-existing worktree changes that must be preserved.

If the request conflicts with `AGENTS.md` (for example, it asks the LLM to
estimate a price, or asks for something listed in §16 Out of Scope), record the
conflict here and raise it with the user before implementing it.

---

## 1. Explore Before Editing

Inspect the relevant code, configuration, data, tests, documentation, and Git
state before implementation. Prefer `rg` and `rg --files` (or the editor's
search tools) for repository searches.

For version-sensitive, high-stakes, niche, or explicitly requested facts, use
an authoritative source: official Anthropic/OpenAI API docs, Microsoft Graph
docs, the Docker or PostgreSQL docs, or the library's own docs. Record the
conclusion and its source in `01-research.md`; do not paste large external
documents into task notes.

During exploration:

- identify ownership boundaries and the smallest safe change surface. Know
  whether the change belongs in deterministic code (`rules/`, `catalog/`,
  `proposal/`) or in an LLM-backed step (`intake/`, `llm/`), and never move
  business logic from the former into the latter;
- identify the applicable `RegionalSpecification` before inspecting or
  changing a rule. A venue's location, customer-selected locale, and the
  jurisdiction declared by approved catalog data—not an LLM inference or a
  developer's assumption—determine which regional catalog and policy pack
  applies;
- find existing conventions (Pydantic models, repository classes, rule
  registration, prompt versioning, logging helpers) before introducing a new
  pattern;
- trace provenance: for any value that reaches a proposal, find where it is
  sourced and confirm the change preserves its `source_ref`;
- for customer-facing or remote-deployment work, trace the trust boundary from
  the public route through the API, agent tools, data stores, and external
  adapters. Confirm that public access cannot reach reviewer-only actions,
  pricing, proposal rendering, approval, export, or source management;
- distinguish generated files (Alembic autogenerate output, rendered DOCX/PDF,
  embeddings, `uv.lock`) from source files;
- identify existing user changes and avoid overwriting or reverting them;
- determine realistic verification commands, including which golden cases and
  which test suites cover the area; and
- do not edit implementation files until the relevant exploration is complete.

Read-only diagnostic commands are allowed at any time. If urgent containment or
a trivial prerequisite must happen first, record why in `04-decisions.md`.

---

## 2. Plan Proportionally

Write `02-plan.md` as short, outcome-oriented phases:

```markdown
## Phase 1: <name>

- [ ] <action with observable completion condition>
- [ ] <verification for this phase>

## Phase 2: <name>

- [ ] <action with observable completion condition>
- [ ] <verification for this phase>
```

Include:

- implementation steps in dependency order (schema/migration → repository →
  rules/pipeline → API → UI → docs is the usual order);
- verification after risky or independently testable phases;
- for accuracy-sensitive work, an explicit phase that runs the golden
  evaluation and compares it with the pre-change baseline;
- for prompt or model changes, a prompt-version bump and a before/after eval;
- compatibility, migration, rollback, or recovery decisions when relevant
  (for example: does an Alembic migration need a downgrade path? Will existing
  draft proposals pinned to an older catalog version still render?);
- explicit acceptance checks for every requested behavior; and
- documentation or handoff work only when the change actually needs it.

Use the editor's TODO mechanism as the concise user-visible plan when useful;
the task file is the durable, detailed record.

Do not automatically stop after planning. Continue implementation when the
user asked to build, change, fix, or complete the task. Pause for approval only
when:

- the user explicitly requested a plan or review before implementation;
- a missing choice would materially change the product, architecture, or a
  business rule (for example: rounding policy, whether service charge is
  taxable, which venue a template belongs to);
- new authorization, credentials, Microsoft 365 permissions, LLM spend beyond
  routine test runs, or external coordination is required; or
- the next action is destructive, irreversible, or meaningfully outside the
  original scope.

---

## 3. Execute in Verifiable Phases

Work through one phase at a time while allowing closely related, independent
checks to run in parallel when safe.

For each phase:

1. Give the user a concise update before tool-driven work.
2. Make the smallest coherent change using the editor's file-edit tools.
3. Preserve unrelated changes and follow `AGENTS.md`.
4. Run focused tests, builds, linting, type checks, or diagnostics appropriate
   to the phase (`uv run pytest <path>`, `uv run ruff check`, `uv run mypy`,
   `Invoke-Pester`).
5. Check off completed items in `02-plan.md`.
6. Add a dated entry to `03-progress.md` containing changes, rationale,
   commands, results, surprises, and the next step.
7. Record only consequential trade-offs or changed assumptions in
   `04-decisions.md`.

Rules that apply during execution:

- **No business numbers in code.** Prices, rates, minimums, staffing ratios,
  tax rates, fees, and capacity limits come from the ingested catalog or from
  `data/rules/`, never from literals in Python, prompts, or templates.
- **No guessed regional behavior.** Currency, language, date/number formatting,
  tax treatment, food-safety/allergen disclosures, service conventions, and
  templates come from an approved, versioned regional specification and
  catalog. The LLM may rank only eligible, region-scoped candidates; it cannot
  infer what is customary or legally required in a location.
- **No LLM-authored facts.** LLM output may populate the structured
  `EventBrief`, choose among candidate IDs supplied by deterministic code, or
  draft clearly marked narrative text. It may not produce prices, quantities,
  menu item text, or venue facts.
- **Customer enquiry channels are intake-only.** The Catering Enquiry
  Assistant may gather event details and present only a clearly non-binding
  submitted-enquiry summary or approved general guidance. It cannot quote,
  confirm availability, issue a proposal, make an execution commitment, or
  invoke reviewer, pricing, approval, export, or source-management actions.
- **Live LLM calls cost money and are non-deterministic.** Default to recorded
  responses in tests; run `-m live` tests or live evals only when the phase
  requires it, and record the model ID and prompt version used.
- **Never modify approved source documents** (pricing workbooks, menus, venue
  templates) in SharePoint/OneDrive or under `data/samples/` to make a test
  pass.

Do not claim a command, environment, deployment, UI path, Microsoft 365
integration, or manual scenario was validated unless it was actually run or
observed. Clearly separate automated verification from checks the user must
perform later.

**Resuming after interruption or context compaction:** read `00-brief.md`, the
unchecked items in `02-plan.md`, the latest `03-progress.md` entry, and open
items in `04-decisions.md`. Recheck `git status` and `git diff` before
continuing, because files may have changed since the notes were written.

---

## 4. Handle Ambiguity and Blockers

Make reasonable, reversible assumptions that stay inside the request, and write
material assumptions in `00-brief.md` or `04-decisions.md`.

**Never resolve a business or regional ambiguity by assumption.** If the
correct price, rule, menu, venue mapping, jurisdiction, currency, language,
format, dietary disclosure, or policy is unclear from approved sources, the
correct implementation surfaces it to the salesperson as a flagged
`NEEDS INPUT` item, and the correct workflow action is to ask the maintainer.
Technical ambiguity (naming, file layout, library choice within the approved
stack) may be resolved by a documented assumption.

Ask the user only when the answer cannot be discovered safely and guessing
could cause:

- incorrect pricing, menu, or venue content in a proposal;
- product or architecture divergence;
- data loss, security exposure, or client-data leakage;
- external side effects (Microsoft 365 writes, LLM spend, emails); or
- substantial rework.

When asking, state:

- what is known;
- the exact missing decision;
- the recommended choice and its consequence; and
- what work can continue without the answer.

Before declaring a blocker, exhaust safe in-scope diagnostics and alternatives.
Record the evidence and the precise condition needed to continue (for example:
"Blocked: Graph returns 403 on the source library; the app registration needs
`Sites.Selected` granted on site X by a tenant admin").

Delegation or subagents are optional tools, not a workflow requirement. Use
them only when the user's request, applicable instructions, and available tools
authorize them and the work can be safely divided.

---

## 5. Verify Against the Brief

Before declaring completion:

1. Re-read `00-brief.md` and the user's latest request.
2. Inspect the final diff and confirm only intended files changed.
3. Run the strongest practical targeted tests, then the broader relevant suite
   or build when proportionate to risk.
4. **For accuracy-sensitive tasks, run the golden evaluation**
   (`uv run python -m evals.run --suite golden`) and compare it with the
   baseline. The release thresholds in `AGENTS.md` §18 apply: exact match on
   priced line items and totals, 100% provenance coverage, zero unsourced menu
   items or figures. Any regression is a failure, not a footnote.
5. Test failure, boundary, recovery, security, and data-preservation paths when
   the change touches them: missing required brief fields, unknown venue,
   guest count outside capacity, menu out of season, stale catalog, Graph
   outage, LLM timeout or malformed tool output.
6. When a task affects regional behavior, test at least two distinct approved
   regional specifications, a boundary between their policies, locale-aware
   currency/date/number rendering, and an unsupported or ambiguous
   jurisdiction. Confirm no record from one region is eligible in another
   without an explicit approved mapping.
7. For customer-facing or remote dedicated-deployment work, verify HTTPS and
   authorization at the deployed boundary; test rate limiting/abuse handling,
   consent and PII redaction, and direct/indirect attempts to invoke internal
   pricing, proposal, approval, export, or source-management routes. Confirm
   that client isolation is preserved for application data, source adapters,
   identity, and backups.
8. Confirm documentation, configuration, `.env.example`, and prompt versions
   match the actual behavior.
9. Record each acceptance criterion in `05-validation.md` as `Passed`,
   `Partial`, `Pending`, or `Not applicable`, with evidence (command plus
   result, or the observed UI behavior).
10. Record any unrun checks and why they were not run (for example: "live
   Graph upload not run, no tenant credentials in this session").

Never weaken, delete, skip, or re-record a failing test or golden expectation
merely to obtain a green result. A golden expectation may change only when the
underlying approved source data changed or the expectation was demonstrably
wrong. Document which one applies and the evidence in `04-decisions.md`.

---

## 6. Write Proper Test Cases Under a Test Suite

Create `06-test-cases.md` when a task adds or changes behavior. Derive every
test case from `00-brief.md`, the acceptance criteria, the affected risks, and
the final implementation. Documentation-only or pure internal refactoring tasks
may mark this section `Not applicable` with a short reason. Even then,
refactors must still pass the existing suites.

Group test cases under the project's standing test suites so coverage stays
navigable:

| Suite ID | Scope |
|---|---|
| `TS-INTAKE` | Free-text brief → `EventBrief` extraction, validation, clarification requests |
| `TS-CATALOG` | Ingestion and validation of venues, menus, price lists; catalog versioning |
| `TS-RETRIEVAL` | Document chunking, embedding, hybrid search, citation of sources |
| `TS-RULES` | Deterministic pricing and business rules, rounding, tax, fees, minimums |
| `TS-PROPOSAL` | Proposal assembly, provenance enforcement, numeric-leak guard |
| `TS-RENDER` | DOCX template filling, PDF conversion, no leftover placeholders |
| `TS-REVIEW` | Reviewer UI, overrides with reasons, approval, audit trail |
| `TS-ENQUIRY` | Catering Enquiry Assistant intake, clarification, non-binding output, public-to-internal authorization boundary, consent, and abuse handling |
| `TS-M365` | Graph authentication, source sync, draft/approved export |
| `TS-REGION` | Regional specification selection, jurisdiction boundaries, locale-aware rendering, regional policy isolation |
| `TS-INSTALL` | Installer state machine, pre-flight, feature enablement, resume/repair/reset |
| `TS-OPS` | Health checks, backup, cleanup, compaction, logging, secret masking |
| `TS-EVAL` | Golden-set end-to-end accuracy against completed proposals |

Use this prompt when preparing the test cases:

```text
Create a requirement-linked test case document for this task. Read 00-brief.md,
02-plan.md, 03-progress.md, 04-decisions.md, the changed implementation, and the
existing test patterns under tests/ and evals/. Group cases under the standing
suite IDs (TS-INTAKE, TS-CATALOG, TS-RETRIEVAL, TS-RULES, TS-PROPOSAL,
TS-RENDER, TS-REVIEW, TS-M365, TS-REGION, TS-INSTALL, TS-OPS, TS-EVAL). For each test case
include: ID (e.g. TS-RULES-014), requirement or risk, test level
(unit/integration/end-to-end/eval/manual), preconditions, test data (sanitized
fixture or golden case ID, never real client data), exact steps, expected
result (exact values for prices and totals), automation location or manual
owner, and current status. Cover the normal path, validation errors,
meaningful boundaries (guest count at venue min/max, season boundary dates,
zero/one menu selected, regional-policy and tax-jurisdiction boundaries,
locale-specific currency/date/number formatting, unsupported jurisdiction),
failure and recovery paths, "never guess" behavior
(missing or ambiguous data must produce NEEDS INPUT, not a value),
permissions/security, compatibility, and data preservation when relevant. Do
not invent execution results. Mark each case Planned, Automated, Passed,
Failed, Blocked, or Manual-Pending and link the actual evidence from
05-validation.md.
```

Keep test cases specific and observable. Do not duplicate low-value
variations, and do not mark a case `Passed` merely because its test code
exists. Move automated cases into `tests/` or `evals/`. The task file is the
index, not the test.

---

## 7. Write a User Manual for User Ease

Create `07-user-manual.md` when the task introduces or changes a user-visible
installation, configuration, operation, recovery procedure, screen, or
workflow. The product has three audiences, and the manual must say which ones
it addresses:

- **Salesperson**: submits an event brief, answers clarification questions,
  reviews the draft.
- **Reviewer/approver**: checks line items and sources, records overrides with
  reasons, approves, exports.
- **Installing administrator**: runs the installer, configures Microsoft 365
  and the LLM provider, manages backups and catalog refreshes.
- **Event enquirer (future)**: uses the Catering Enquiry Assistant to submit
  event requirements; receives only a non-binding acknowledgement or summary.

Use the task file as a reviewed draft during the task. Before completion, move
lasting instructions into `docs/user-manual/` (one file per audience or
feature). Do not make the scratch task folder the only location of the user
manual.

Use this prompt when preparing the user manual:

```text
Write a user manual for the behavior delivered by this task. Base it only on the
verified implementation and 05-validation.md. Identify the intended audience
(salesperson, reviewer, or installing administrator), prerequisites, supported
environment, required Microsoft 365 permissions, and any safety warning. Give
numbered steps for setup and normal operation, explain the visible result after
each important action, and explain how to read flagged items (NEEDS INPUT,
source links, override history). Include recovery, backup/restore,
troubleshooting, catalog refresh, and uninstall/reset guidance only when
relevant. Use the exact labels, button names, and paths shown by the product.
Add screenshot placeholders only where a visual is truly needed. Never include
secrets, real client data, developer-only commands, unsupported promises, or
steps that were not verified. State plainly that the system drafts proposals
and a salesperson must review and approve every proposal before it is sent.
Clearly label administrator actions, destructive actions, known limitations,
and manual checks.
```

Review the manual against the finished product and the supported platform.
Any unverified instruction must be labeled clearly rather than presented as
tested.

---

## 8. Wrap Up

The final response should lead with the outcome and include only what helps
the user continue:

- what changed and why;
- the most important files as clickable paths;
- tests, checks, and golden-eval results that passed or failed (with numbers);
- any change in model ID, prompt version, catalog schema, or migration head;
- unresolved limitations, manual checks, business questions awaiting an
  answer, or follow-up work; and
- destructive or unrecoverable actions taken, if any.

Keep the task folder by default so future sessions can recover the work
history. Task folders are Git-ignored and must not be referenced from product
documentation or treated as permanent design records. Promote lasting
decisions to `docs/adr/NNNN-<title>.md` (architecture), `AGENTS.md` (agent
rules, with maintainer sign-off), or `docs/user-manual/` (user procedures).

Delete task scratch only when the user requests cleanup or a repository
retention policy explicitly requires it. Before deletion, ensure no unique
decision or validation evidence exists only in scratch.

---

## 9. Standing Rules

- Preserve user intent and authorization boundaries.
- Accuracy over automation: when in doubt, the system flags and asks; it never
  guesses. The same applies to you as the implementing agent.
- Global does not mean generic facts: every recommendation is constrained by
  the selected, approved `RegionalSpecification`; the system must not infer
  culture, law, taxes, cuisine, language, or currency from geography or prose.
- The dedicated client deployment is the product boundary: never introduce a
  shared cross-client data store or multi-tenant behavior without explicit
  maintainer sign-off and a security design. Treat the Catering Enquiry
  Assistant as a separate public trust boundary, never as a shortcut into the
  internal proposal portal.
- Every value in a proposal must trace to an approved source (`source_ref`) or
  to a reviewer override with a recorded reason.
- Keep business logic deterministic and testable; confine the LLM to
  extraction, constrained selection, and clearly marked narrative.
- Explore and plan in proportion to task complexity and risk.
- Prefer several coherent, verifiable phases over one large unverified change.
- Keep `03-progress.md` current enough to resume after an interruption.
- Use `04-decisions.md` for meaningful decisions, not routine implementation
  details.
- Never revert or overwrite unrelated user changes.
- Never use destructive Git, database, Docker volume, or Microsoft 365
  commands without explicit authorization.
- Never put secrets or real client data in code, fixtures, logs, prompts
  committed to the repo, or task notes.
- Treat tests, golden evals, logging, error messages, migrations, audit
  records, and recovery behavior as product behavior; users depend on them.
- Do not let task-note maintenance become more work than the task itself.
