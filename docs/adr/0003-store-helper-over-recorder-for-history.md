# ADR 0003: Use Home Assistant's `Store` Helper (Not Recorder) for Portfolio History

**Status:** Accepted — deferred to Milestone 7 (not implemented yet)
**Date:** 2026-07-09

## Decision

When historical data (transaction log, daily snapshots) is implemented, it will be persisted via `homeassistant.helpers.storage.Store`, not relied upon from the Recorder's entity-state history or long-term statistics.

## Reason

Recorder is designed for HA entity-state history and is subject to `purge_keep_days`, database backend limits, and general-purpose retention policies the user doesn't control from this integration. Financial records (transactions, point-in-time snapshots for time-weighted-return calculation) need indefinite, authoritative retention independent of the user's Recorder configuration — losing them because someone lowered `purge_keep_days` for unrelated reasons would be a real defect, not an acceptable tradeoff.

## Alternatives Considered

- **Rely on Recorder long-term statistics for `sensor.portfolio_value` history** — kept as a *complementary* source for simple "value over time" charts (cheap, already built, fine for that narrow purpose), but rejected as the system of record because statistics store scalar values only, not portfolio composition, and are still subject to the user's recorder configuration in ways transaction records shouldn't be.
- **External database (SQLite/Postgres) for history** — more powerful, but adds an operational dependency (schema migrations, backup strategy) disproportionate to the milestone this is needed for. `Store` is zero-additional-infrastructure and consistent with "prefer the simpler implementation unless the abstraction clearly enables future functionality" — here it does (TWR/MWR genuinely need it) but the *storage mechanism* itself should stay as simple as HA already provides.

## Consequences

- Transaction/snapshot data survives independent of Recorder settings and full HA reinstalls that don't restore the database, as long as `.storage/` is backed up (already true for essentially all HA config).
- No query language — `Store` is JSON blobs. Acceptable at personal-portfolio data volumes (thousands of transactions, not millions); would need revisiting if this ever needed to scale beyond one household's data.
- This ADR documents the decision ahead of implementation (Milestone 7) intentionally, so the reasoning isn't rediscovered under time pressure later.
