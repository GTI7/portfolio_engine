# ADR 0005: Defer Event-Driven Recalculation

**Status:** Accepted
**Date:** 2026-07-09

## Decision

Milestone 1 (and subsequent milestones, until explicitly revisited) uses a straightforward coordinator refresh cycle: on each poll interval, fetch all data and recompute all registered calculators. No internal event bus, no per-symbol partial recalculation.

## Reason

Full recomputation on every tick is simple to write, simple to reason about, and simple to test — for a personal portfolio (tens of holdings, a 15-minute poll interval), the cost of recomputing everything is negligible. An event-driven engine (separate `PRICE_UPDATED`/`HOLDING_CHANGED`/etc. events, calculators declaring which events they react to) is real added complexity that only pays for itself once recomputation cost is actually measured to be a problem — which it is not, yet, since Milestone 1 has no production usage data to justify it against.

## Alternatives Considered

- **Build the event bus now, since it's in the target architecture** — rejected for this milestone specifically; the target architecture document lists it as a documented future optimization, not a day-one requirement, and introducing it before there's a coordinator to attach it to would be building on nothing.

## Consequences

- Simpler code path for Milestone 1–5: one `_async_update_data()`, no event subscription bookkeeping.
- If/when portfolio size or poll frequency makes full recomputation measurably expensive (this should be observed via the diagnostic `refresh_duration` sensor from Milestone 2, not guessed at), Section 4 of the architecture document describes the event-driven upgrade path already designed for that point — this ADR does not preclude it, it just declines to build it before it's needed.
