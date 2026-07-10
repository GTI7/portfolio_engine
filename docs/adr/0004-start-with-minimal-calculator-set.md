# ADR 0004: Start With a Minimal Calculator Set

**Status:** Accepted
**Date:** 2026-07-09

## Decision

Milestone 1 implements exactly three calculators — `PortfolioCalculator` (value, cost basis, gain, ROI), `AllocationCalculator` (grouping by any holding attribute), and `PerformanceCalculator` (day/period change, stubbed until history exists in later milestones). `DividendCalculator`, `RiskCalculator`, `GoalCalculator`, and `TaxCalculator` are **not** created as empty classes — they're added when their underlying data (dividend feed, transaction history, goal input) actually exists to calculate from.

## Reason

The `Calculator` plugin architecture (see project architecture doc, Section 5) makes adding a calculator cheap later — that's the point of the abstraction. Pre-creating empty calculator stubs "for later" buys nothing (there's no logic to test, no interface friction it prevents) while adding surface area to maintain and dashboard placeholders pointing at sensors with no real data. This directly follows the stated principle: prefer delivering a stable, tested feature over adding an abstraction whose payoff isn't immediate.

## Alternatives Considered

- **Scaffold all seven calculators now as stubs returning empty/zero results** — rejected; produces dashboards that look complete but show fake zeros, which is worse than a dashboard tab that simply doesn't exist yet.
- **Implement everything in one `PortfolioCalculator` god-class, skip the plugin architecture entirely** — rejected; the modular boundary is cheap to establish now (three small classes instead of one large one) and expensive to retrofit later once dashboards and tests depend on a monolithic calculator's internal structure.

## Consequences

- Dividends, risk metrics, goal tracking, and tax reporting are simply absent from the dashboard until their milestones land — no placeholder UI, no misleading data.
- Each new calculator, when its turn comes, is additive: implement `Calculator`, register it, add its dashboard view. No changes to `PortfolioEngine`, existing calculators, or the repository/provider layers.
