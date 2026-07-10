# ADR 0008: Cash as a First-Class Portfolio Concept

**Status:** Accepted
**Date:** 2026-07-09

## Decision

`Portfolio` gains a `cash_balance: float` field (base currency, validated non-negative). The `Calculator` interface changes from `calculate(positions, base_currency)` to `calculate(portfolio, positions)` so every calculator has access to cash, not just the ones that happen to need it today. All three Milestone-1 calculators now account for cash: `PortfolioCalculator` includes it in `total_value` (but not `roi_pct`, which is invested-capital-only by definition), `AllocationCalculator` emits a `"Cash"` group so allocation percentages sum to 100 including cash, and `PerformanceCalculator` includes it in the weighting denominator (contributing an implicit 0% change).

## Reason

Cash was absent from the Milestone 1 domain model entirely — discovered during Milestone 2 planning when `sensor.portfolio_cash_balance` had nothing to bind to. Treating it as a bolted-on special case (e.g. a separate `cash_balance` parameter threaded through only the calculators that need it, or worse, a fake zero-share "CASH" holding) would work for one sensor today but actively works against every later feature that needs to reason about the whole portfolio: allocation percentages would either exclude cash (misleading — a 30%-cash portfolio would show as 100% invested) or need special-casing per calculator; goals and total-value tracking would need their own separate cash lookup; snapshots (Milestone 7) would need to remember to capture it as a second, differently-shaped value. Making it a `Portfolio` field now means every current and future calculator sees it automatically, for free, through the same interface.

## Alternatives Considered

- **Cash as a synthetic zero-share `Holding`** (`type: "cash"`, `shares: <balance>`, `avg_price: 1`) — rejected. It would technically flow through the existing per-holding math without an interface change, but it's a type-system lie: cash has no `symbol` to fetch a `Quote` for, no `avg_price` in any meaningful sense, and `gain_pct`/`day_change_pct` are undefined for it. Every consumer of `Position` would need to special-case "unless this is the fake cash holding," which is worse than an honest model field.
- **Cash as a separate parameter passed only to the calculators that need it** — rejected as inconsistent with treating the `Calculator` interface as the single way calculators receive portfolio state; some calculators taking an extra argument and others not is exactly the kind of interface drift that makes a plugin architecture (Section 5 of the architecture doc) harder to reason about over time.
- **Leave cash out of Milestone 2, add it in a later milestone once needed elsewhere** — rejected per explicit guidance: retrofitting a domain-model field after entities and dashboards depend on the old shape is more disruptive than a synchronous model change now, before Milestone 2's sensors exist.

## Consequences

- `Calculator.calculate()`'s signature change is a breaking change to the engine's own internal interface. Since the engine is pre-1.0 and versioned independently (ADR-0007), this is a minor version bump (`0.1.0` → `0.2.0`), not a concern requiring a deprecation path — there are no external consumers of this interface yet.
- `holdings.yaml` gains one new optional top-level field (`cash_balance`, defaulting to `0.0` if omitted) — additive, not a breaking change to the data layer.
- Every future calculator (Dividend, Risk, Goal, ...) inherits cash-awareness automatically through the same `Portfolio` parameter, with no additional plumbing required when those land.
