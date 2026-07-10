# ADR 0001: Repository Pattern for Portfolio Data

**Status:** Accepted
**Date:** 2026-07-09

## Decision

The engine retrieves portfolio data (holdings, and later transactions) exclusively through a `PortfolioRepository` interface. It never reads YAML files, databases, or APIs directly.

## Reason

The initial design (v1/v2) had the coordinator read `holdings.yaml` directly. That's fine for a single fixed data source, but the stated long-term requirement is to support multiple backing stores (local YAML, JSON/SQLite, broker APIs, cloud sheets) "without modifying the engine." A repository interface is the standard pattern for exactly that: the engine depends on an abstraction, not a file format.

## Alternatives Considered

- **Read YAML directly in the coordinator** — simplest, but ties the engine's data-loading logic to one format; swapping to a broker API later would mean rewriting the coordinator rather than adding a file.
- **ORM-style active-record models** — overkill for read-mostly config data with no relational structure; adds a dependency and a learning curve for no real benefit here.

## Consequences

- Every new data source (JSON, broker, cloud sheet) is a new class implementing 1–2 methods, not a change to the engine or coordinator.
- Repositories are strictly I/O: fetch and (later) persist. Business logic — computing value, gain, allocation — must never live in a repository (see ADR-0002 for the corollary on providers, and the engine's own responsibility boundary).
- Adds one extra layer of indirection versus "just read the file," which is a real (small) cost for the current single-source-of-truth (YAML) case. Accepted because the requirement to swap sources later is explicit, not speculative.
