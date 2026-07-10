# Milestone 6: Snapshot Engine + Time-Weighted Return (TWR)

**Status:** Complete for the agreed six-phase scope. No spec document — same reasoning as Milestone 5: the scoping message was detailed enough to implement directly from, with phase discipline (tests gating each transition) as the substitute for a written spec.

## Phases, as executed

| Phase | What shipped | New tests | Cumulative (engine) |
|---|---|---|---|
| 1. Snapshot domain model | `HoldingSnapshot`, `Snapshot` (validation + `to_dict`/`from_dict`), `Portfolio.snapshots` | 23 | 183 |
| 2. Snapshot repository | `SnapshotRepository` interface, `InMemorySnapshotRepository`, ADR-0012 | 9 | 192 |
| 3. Snapshot collection | `engine/snapshot_policy.py` (`should_create_snapshot`, `build_snapshot`) | 8 | 200 |
| 4. TWR engine | `TwrCalculator` (7th calculator), `engine/external_cash_flows.py` (factored out of `MwrCalculator`) | 15 | 216 |
| 5. HA integration | `StoreSnapshotRepository`, coordinator/`update_logic.py`/`sensor.py`/`sensor_mapping.py`/`diagnostics.py` wiring, new entity | +6 pure-logic, +7 real-HA-harness | — |
| 6. Benchmarking | Two-dimensional benchmark (holdings count, snapshot-history length) | — | — |

**279 tests total**, up from 210 at Milestone 5.

## The one new ADR

**ADR-0012** — `SnapshotRepository` as a separate interface from `PortfolioRepository`, with `StoreSnapshotRepository` as the first real `Store`-backed persistence in this project. This is the moment ADR-0003 (Milestone 1) was written for: Recorder was ruled out for financial history back then, `Store` was named as the eventual right answer, and this milestone is where that actually gets built rather than deferred again. The full reasoning — why snapshots are self-generated operational data rather than user/external-declared config, why that argues for a separate interface, why `update_logic.py` (not `PortfolioRepository`) is what attaches `Portfolio.snapshots` — is in the ADR itself, not just this summary.

## Two real bugs, both caught by tests before reaching the integration layer

Consistent with every prior milestone's pattern: found by writing hand-verified tests and a real benchmark, not discovered later.

1. **A sign-convention bug in `TwrCalculator`.** `extract_external_cash_flows` (shared with `MwrCalculator`) uses the MWR/NPV sign convention — negative means capital flowing into the portfolio, since that's an outflow from the investor's perspective. TWR's formula needs the *opposite* framing: a deposit inflates the portfolio's own value and must be *subtracted* to isolate growth, which requires a positive figure. Using the raw MWR-convention sign produced a -45% result where hand-calculation said -5%. Caught by `test_withdrawal_correctly_excluded` on the very first test run of `TwrCalculator`, before any HA-layer code existed. Fixed by explicitly negating the sign at the point of use, with the reasoning now documented inline (`period_injection = -sum(...)`) rather than left implicit.
2. **A real O(n×m) performance issue in `TwrCalculator`**, caught by the Phase 6 benchmark work specifically because the benchmark was built correctly. The original implementation re-scanned every external cash flow for every snapshot period. The first version of the snapshot-history benchmark didn't expose this — it used a single opening deposit regardless of history length, so flow count never grew. Extending the benchmark to add a deposit every 30 days (so flow count scales *with* history length, the realistic case) exposed genuinely worse-than-linear behavior. Fixed with a single sorted merge-pass over periods and flows (O(periods + flows)), confirmed behaviorally identical against all pre-existing hand-verified TWR tests plus two new ones covering the edge cases the rewrite had to get right (flows before the first snapshot; many flows across many periods). Full before/after numbers in `BENCHMARKS.md`.

## Design decisions worth surfacing

- **The synthetic "current value" period.** `TwrCalculator` (like `MwrCalculator`) extends the last real `Snapshot` to the live current portfolio value at `as_of`, rather than only reporting TWR as of last night's snapshot. This means a portfolio with exactly one snapshot is still computable (one real period: snapshot → now), not stuck at `insufficient_data` until a second daily snapshot exists.
- **`update_logic.py`'s first signature change since Milestone 3.** Snapshots come from a second, independent repository (`SnapshotRepository`, not `PortfolioRepository`), so `update_logic.async_fetch_portfolio_data()` gained a `snapshot_repository` parameter and now composes both repositories at the call site — the same pattern it already used for the price/currency providers, applied to a third independent dependency.
- **Snapshot creation happens after the engine runs, not before.** The newly-created snapshot for "today" is deliberately not added to `portfolio.snapshots` for the current run's `TwrCalculator` — it would be redundant with the synthetic current-value period already covering today. It becomes a real historical boundary starting the next refresh.

## Validation checklist

- [x] `Snapshot`/`HoldingSnapshot` implemented with full validation, serialization, and migration-safety tests (a missing `holdings` key in an older-schema dict still loads)
- [x] `SnapshotRepository` interface + `InMemorySnapshotRepository`: load, save, ordering, duplicate-ID rejection, migration safety
- [x] `should_create_snapshot`/`build_snapshot`: first snapshot, duplicate prevention (same calendar date), gaps in history don't confuse the check
- [x] `TwrCalculator`: hand-verified multi-period examples (deposit and withdrawal cases independently verified), no snapshots, one snapshot (both with and without elapsed time), missing intervals (a full-year gap), cash-flow-exactly-at-boundary edge case, not-computable (zero-value period start)
- [x] `sensor.<portfolio>_time_weighted_return` entity: registration/device grouping, `unknown` on first-ever setup, `ok` computation with a pre-seeded prior snapshot, diagnostics block
- [x] Diagnostics: snapshot count, latest snapshot, TWR status — all present
- [x] Real HA-harness tests: entity registration, `unknown` state, valid computation, diagnostics, **and** a genuine restart-behavior test (full unload/setup cycle against the same persisted `Store` data, confirming no duplicate snapshot)
- [x] Benchmark extended to two independent dimensions (holdings count, snapshot-history length) — the second dimension is what actually caught the O(n×m) issue
- [x] `ruff check` / `mypy` clean throughout
- [x] `docs/adr/0012-...md` written
- [x] No changes to `config_flow.py`, `PortfolioRepository`, `PriceProvider`, `CurrencyProvider`, or the `Calculator` interface signature

## What was deliberately not included

Per the roadmap agreed alongside this milestone: seven calculators is treated as the practical ceiling for this "data platform" phase (`coordinator.py`'s `_build_engine()` now says so explicitly). No dividend yield/income, CAGR, volatility, drawdown, Sharpe ratio, or benchmark comparison — those are Milestone 7 ("Analytics"), which consumes this platform rather than extending it. No annualized TWR (CAGR) — `TwrResult.twr_pct` is explicitly cumulative; annualizing is additive future work, not a redefinition. No broker/CSV imports, write services, tax-lot accounting, or multi-portfolio aggregation — unchanged from every prior milestone's deferral list.

## How to validate

```bash
python -m pytest tests/ tests_integration/ -q   # 242 passed
./.ha_test_venv/bin/python -m pytest tests_ha/ -q   # 37 passed
python -m ruff check . custom_components/ tests_ha/ scripts/
python -m mypy
python scripts/benchmark.py --sizes 100,500,1000 --snapshot-days 100,500,1000,2000 --repeats 20
```

## What's next

Per the agreed roadmap: Milestone 7 ("Analytics") — dividend yield/income, CAGR, volatility, drawdown, Sharpe ratio, benchmark comparison — building on the data platform Milestones 1–6 established, rather than extending it further. `MANUAL_VALIDATION_RUNBOOK.md` also remains the one item flagged since Milestone 2.5 as not yet executed against a real, persistent HA instance — now with Recorder statistics on `SensorStateClass.MEASUREMENT`/`TOTAL` entities and restart persistence both genuinely more interesting to verify for real, given this milestone's Store-backed persistence and multi-day snapshot history.
