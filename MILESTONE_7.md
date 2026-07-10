# Milestone 7: Portfolio Analytics

**Status:** Complete for the exact scope in `MILESTONE_7_DESIGN.md` / the implementation brief. Four new calculators, one new shared helper, one existing entity gained an attribute — nothing else touched.

## What's included

- **`engine/period_returns.py`** — the cash-flow-excluded sub-period return series extracted out of `TwrCalculator`'s internals (Milestone 6), now shared with `VolatilityCalculator`. `TwrCalculator`'s full pre-existing test suite (15 tests) passed unmodified against the refactored implementation before anything else was built — the correctness gate for the extraction.
- **`TwrResult.annualized_pct`** (CAGR) — an attribute on the existing `sensor.<portfolio>_time_weighted_return` entity, not a new entity. This is exactly what Milestone 6 left `twr_pct` cumulative (not annualized) to enable.
- **`DividendCalculator`** → `sensor.<portfolio>_dividend_income`. Rolling-12-month state; lifetime, current-year, yield, average-monthly in attributes.
- **`DrawdownCalculator`** → `sensor.<portfolio>_drawdown`. Current drawdown state; maximum drawdown, peak value/date, recovery status in attributes. The one calculator that deliberately does *not* use `period_returns.py` — drawdown is a statement about the raw value line, which deposits/withdrawals should be allowed to move, unlike the return metrics.
- **`VolatilityCalculator`** → `sensor.<portfolio>_volatility`. Annualized volatility state; unannualized figure and sample size in attributes.
- **`PositionAnalyticsCalculator`** → `sensor.<portfolio>_concentration`. Largest-position-% state; largest winner/loser, top-5 concentration, diversification score, and Herfindahl-Hirschman index in attributes.

Eleven calculators, fourteen entities, after this milestone.

## One real bug, caught before reaching HA — same pattern as every prior milestone

`DividendCalculator`'s first implementation filtered future-dated dividends (relative to `as_of`) out of the rolling-12-month and current-year figures, but not out of `lifetime` or `average_monthly_dividend`. Caught while writing `test_dividends_after_as_of_are_ignored`, before any HA-layer code existed. Fixed by filtering the whole dividend list to `date <= as_of` once, upfront, so every downstream figure is consistently correct — not four separate ad-hoc filters that could drift out of sync with each other.

## A genuine negative result on the benchmark

Unlike Milestone 6, extending the benchmark to all 11 calculators and re-running both scaling dimensions (holdings count, snapshot-history length) found **no algorithmic issue**. Both dimensions stayed linear-to-sub-linear across two independent 20-repeat confirming runs. Worth recording as a real check that came back clean, not silently skipped — `VolatilityCalculator` specifically inherits `period_returns.py`'s already-fixed O(periods + flows) scaling rather than risking a second O(n×m) bug in a different calculator making the same mistake `TwrCalculator` originally made.

## Two attribute names chosen to match the implementation brief exactly, worth noting

Both differ slightly from `MILESTONE_7_DESIGN.md`'s own draft, which I revised to follow the brief once it was more specific than my design pass:

1. **`herfindahl_index`/`diversification_score` are both attributes on `PositionAnalyticsCalculator`.** My design draft had rejected HHI entirely as "not something anyone can look at and immediately understand." The brief asked for it explicitly as an attribute (not the entity's *state*, where that readability concern still applies) — a reasonable middle ground I hadn't considered: HHI is useful to someone who knows what it is, and costs nothing to expose as a supplementary attribute once `diversification_score` (its more legible 0–100 rescaling) is already the primary supporting figure.
2. **`DrawdownResult` uses `recovery_status`** (`"at_peak"`/`"recovering"`/`"in_drawdown"`) instead of the generic four-way `status` field every other Milestone 5–7 result type uses. This is deliberate, not an inconsistency: `recovery_status` answers a genuinely different question ("where am I in a recovery cycle") than `status` ("was this even computable") — `DrawdownResult` still has its own separate `status` field (`"ok"`/`"no_data"`) for the latter question, per its own docstring explaining why `"insufficient_data"` never applies here (a single snapshot is already enough to compute a trivial "at peak" reading).

## Validation checklist

- [x] `DividendCalculator`, `DrawdownCalculator`, `VolatilityCalculator`, `PositionAnalyticsCalculator` implemented and registered — 11 calculators total
- [x] `period_returns.py` extracted; `TwrCalculator`'s full existing test suite passes unmodified
- [x] `TwrResult.annualized_pct` added; existing TWR entity/tests updated, no new entity
- [x] Four new entities implemented with `docs/ENTITY_CONTRACTS.md` entries, each following the "one entity, rich attributes" shape — no additional entities
- [x] `PortfolioHealthCalculator`, Sharpe ratio, Sortino ratio, Beta, Alpha, benchmark comparison, sector analytics, ESG metrics, goal tracking, risk scoring, broker integrations, CSV imports, AI insights — none implemented, matching the brief's explicit out-of-scope list exactly
- [x] All three test categories updated; 337 tests total (up from 279)
- [x] `ruff check` / `mypy` clean throughout
- [x] `BENCHMARKS.md` re-run and updated — two dimensions, both checked, neither showed a regression
- [x] `CHANGELOG.md` updated
- [x] No new ADR — checked explicitly against the "genuine fork, real alternatives" bar; nothing here clears it
- [x] No coordinator changes beyond registering four calculators; no provider/repository/config-flow/`Calculator`-interface changes

## How to validate

```bash
python -m pytest tests/ tests_integration/ -q   # 293 passed
./.ha_test_venv/bin/python -m pytest tests_ha/ -q   # 44 passed
python -m ruff check . custom_components/ tests_ha/ scripts/
python -m mypy
python scripts/benchmark.py --sizes 100,500,1000 --snapshot-days 100,500,1000,2000 --repeats 20
```

## What's next

Per the brief's own closing line: this milestone should demonstrate the plugin architecture scales naturally as analytical capabilities are added — eleven calculators registered in `coordinator.py` with a four-line addition, zero changes to any other architectural layer, is that demonstration. `coordinator.py` itself now states no further calculators are planned without a design pass first. `MANUAL_VALIDATION_RUNBOOK.md` remains the one item flagged since Milestone 2.5 as not yet executed against a real, persistent HA instance.
