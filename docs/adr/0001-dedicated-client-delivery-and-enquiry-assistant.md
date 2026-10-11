# ADR 0001: Dedicated Client Delivery and Catering Enquiry Assistant

**Status:** Accepted

**Date:** 2026-10-12

## Context

The platform needs a clear client-delivery model and a safe way to distinguish
the internal proposal workflow from future customer event enquiries. The
prototype already has strict rules: it is localhost-only, its pricing and
proposal pipeline is human-reviewed, and it never sends proposals to clients.

## Decision

- Deliver the product as a dedicated, client-isolated web application. Each
  client has an isolated application deployment, database, catalog, source
  adapters, identity configuration, and backup boundary.
- Keep the authenticated internal proposal portal as the initial delivery
  channel.
- Name the future customer-facing intake experience the **Catering Enquiry
  Assistant**. It can collect event requirements and return a clearly
  non-binding acknowledgement or summary only.
- The Catering Enquiry Assistant is not a proposal or quotation channel. It
  cannot confirm availability, calculate or quote prices, issue proposals,
  approve/export proposals, access source documents, or use reviewer
  privileges.
- Defer PWA packaging, native mobile apps, and app-store distribution.

## Consequences

- The existing Windows/Docker localhost proof of concept remains unchanged;
  this decision does not authorize remote or public exposure.
- A production remote deployment and a public enquiry channel require separate
  implementation and security review, including HTTPS, authorization
  separation, client isolation, consent/PII controls, and abuse protection.
- Multi-tenant SaaS and shared cross-client databases are out of scope unless
  explicitly reconsidered in a later ADR.
