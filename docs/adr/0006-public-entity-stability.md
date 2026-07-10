# ADR 0006: Treat Exposed Entity IDs as a Stable Public API

**Status:** Accepted
**Date:** 2026-07-09

## Decision

Milestone 2 exposes a minimal, deliberately small set of entities — `sensor.portfolio_value`, `sensor.portfolio_total_invested`, `sensor.portfolio_total_profit`, `sensor.portfolio_roi`, `sensor.portfolio_cash_balance` (plus one attribute-bearing positions entity for table rendering). Once an entity ID ships, it is treated as a stable public interface: it is not renamed or removed in later milestones. New data is exposed by adding new entities, not by changing what an existing entity ID means or what type its state holds.

## Reason

Dashboards, automations, and any Lovelace YAML a user writes reference entity IDs directly. Home Assistant's own integrations follow this convention for exactly this reason: renaming or repurposing an entity silently breaks every automation and dashboard that depended on it, and the breakage often isn't visible until the automation fails to fire. The Portfolio Engine's internal structure (calculators, models) is free to be refactored aggressively — that's the entire point of keeping calculation logic behind the engine boundary — but the entities the coordinator/sensor platform exposes to the rest of Home Assistant are the integration's actual contract with its users, and contracts don't get to change for free.

## Alternatives Considered

- **Expose every calculator's full output as entities immediately** (all of `PortfolioSummary`, `AllocationGroup` breakdowns, per-position sensors, etc.) — rejected. A large initial entity surface makes every future internal refactor a potential breaking change, and most of that data belongs in attributes anyway (see the hybrid entity model in the architecture doc), not as separately named entities that then need to be individually maintained forever.
- **Version entity IDs** (e.g. `sensor.portfolio_value_v2` on breaking change) — rejected as the default strategy; it works for genuine breaking changes but should be the exception, not the plan. The point of this ADR is to avoid needing it by getting the initial surface right and additive from here.

## Consequences

- Milestone 2's entity list (Section "Guidance for Milestone 2" in the project notes) is intentionally conservative — five dedicated sensors plus one positions/attributes entity. Expanding it later (allocation entities, dividend entities, per-portfolio entities once multi-portfolio lands) is always safe: new entity IDs, never renamed existing ones.
- If a genuine breaking change is ever unavoidable (e.g. a unit-of-measurement correction that changes what a state number means), it must go through Home Assistant's own entity-migration mechanisms (unique_id-based registry updates, repair issues informing the user) rather than a silent rename — this is the standard HA integration pattern and applies here too.
- This constrains the sensor platform, not the engine. `engine/` can rename `PortfolioSummary.roi_pct` to anything it likes internally as long as `sensor.py` keeps mapping it to `sensor.portfolio_roi`.
