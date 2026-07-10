# Milestone 2 Plan (not yet implemented)

Recorded now, per review feedback, so Milestone 2 starts from an agreed
scope — specifically the minimal-entity-surface constraint from ADR-0006 —
rather than that constraint being applied retroactively after entities
already shipped.

## Entity surface (the integration's public API — see ADR-0006)

Only these ship in Milestone 2:

| Entity | Source | Type |
|---|---|---|
| `sensor.portfolio_value` | `PortfolioSummary.total_value` | dedicated |
| `sensor.portfolio_total_invested` | `PortfolioSummary.total_invested` | dedicated |
| `sensor.portfolio_total_profit` | `PortfolioSummary.total_unrealized_gain` | dedicated |
| `sensor.portfolio_roi` | `PortfolioSummary.roi_pct` | dedicated |
| `sensor.portfolio_cash_balance` | (new: cash balance input, not yet modeled — see Open Questions) | dedicated |
| `sensor.portfolio_positions` | `positions` list from `PortfolioEngine.run()` | attribute-only (holdings table data) |

Explicitly **not** shipping yet, even though the engine already computes some of it: allocation-breakdown entities, performance (day/weekly/monthly) entities, diagnostic entities. These land in later milestones once there's a concrete dashboard consuming them — per the same "don't build ahead of need" principle applied to Milestone 1's calculators (ADR-0004), applied here to entities.

## Scope for Milestone 2 itself

- `custom_components/portfolio_engine/manifest.json`, `const.py`
- `config_flow.py` — initial setup: provider choice (Yahoo Finance only for now), base currency, holdings path
- `coordinator.py` — `DataUpdateCoordinator` wrapping `YamlRepository` + `YahooFinanceProvider` + `PortfolioEngine`, full recompute per tick (ADR-0005 — no event bus yet)
- `sensor.py` — the six entities above, with proper `DeviceInfo`, `unique_id`, and `SensorDeviceClass`/`state_class` set correctly for the numeric ones (so HA's own statistics work on `sensor.portfolio_value` for free — relevant later for TWR/MWR per ADR-0003)
- Tests: coordinator update logic, sensor state mapping — using HA's test harness (`pytest-homeassistant-custom-component`), separate from the engine's own HA-independent test suite

## Explicitly out of scope for Milestone 2

`OptionsFlow` for ongoing tuning, diagnostics platform, hot-reload-on-file-change, repairs — these are real requirements from the broader architecture but are follow-on within "HA wiring," not required to get a first working, testable increment. They'll be sequenced as Milestone 2b/2c rather than blocking Milestone 2's initial delivery, consistent with "I would rather have eight completed milestones than one partially finished architecture."

## Open questions to resolve before starting

1. **Cash balance** isn't in the Milestone-1 domain model at all (no `Holding` represents cash, and there's no `Portfolio.cash_balance` field). Needs a small model addition — likely a `cash_balance: float` field on `Portfolio`, sourced from `settings.yaml` per the original architecture doc — before `sensor.portfolio_cash_balance` can be wired up. This is a one-field addition, not a redesign, but it should happen deliberately at the start of Milestone 2 rather than be discovered mid-implementation.
2. Confirm `SensorDeviceClass.MONETARY` + `state_class: total` is the right HA convention for `portfolio_value`/`total_invested`/`total_profit` (vs. `measurement`) — affects how HA's own statistics/energy-dashboard-style long-term storage treats them, which matters for the eventual TWR/MWR work in Milestone 7.
