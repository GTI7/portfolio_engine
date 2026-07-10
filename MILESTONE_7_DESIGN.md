# MILESTONE_7_DESIGN.md — Portfolio Analytics

Design only — no implementation in this pass. Purpose: decide which analytics become calculators, which become plain helper functions, which outputs become entities, and which stay diagnostics-only, before writing any code. Kept short deliberately — this is a scoping pass, not a spec on the scale of `MILESTONE_4_SPEC.md`.

## Starting position

Seven calculators exist (Summary, Allocation, Performance, Reconciliation, Transactions, MWR, TWR). `coordinator.py` currently states seven is the practical ceiling for the "platform" phase. This document is what justifies growing past that number now — Milestone 6 explicitly named this as the next milestone's job.

## The five candidates from the advisory, and what each becomes

### 1. Dividend analytics → new calculator, one entity

**Calculator: yes.** Multiple related outputs (lifetime, rolling 12-month, this-year, yield-on-cost, yield-on-value) sharing one data source (`DIVIDEND` transactions, already present, no new transaction type) is exactly the shape of the existing calculators — a focused, independently testable unit.

**Entity: one.** `sensor.<portfolio>_dividend_income`.
- State: rolling-12-month dividend income (the most actionable single number — "lifetime" only grows and stops being interesting after a few years; "this calendar year" resets awkwardly every January).
- Attributes: `lifetime_total`, `this_year_total`, `yield_on_cost_pct`, `yield_on_value_pct`.
- Unit: base currency. State class: `measurement` (a rolling window, not a monotonic total — using `total`/`total_increasing` would tell HA's statistics engine something false about how this number behaves over time).

**Helper vs. calculator:** the date-window filtering (rolling 12 months, calendar year) stays inline in `DividendCalculator`. No second consumer exists yet, so no extraction — same rule already applied elsewhere in this project (a helper gets factored out when a *second* caller needs it, not preemptively; `external_cash_flows.py` was extracted because two calculators needed it, not because extraction is generally good practice).

### 2. CAGR → NOT a calculator or entity — an attribute on the existing TWR entity

**Calculator: no.** CAGR is TWR's cumulative return, annualized over the elapsed period. `TwrResult.twr_pct` was deliberately left cumulative rather than annualized specifically so a future annualized figure could be added without redefining what the existing field means (Milestone 6's own docstring says this explicitly). Making CAGR a state field on the *existing* TWR entity fulfills that plan directly; making it a separate `CagrCalculator` + new entity would mean two entities answering almost the same question, which is the exact sprawl this design pass exists to avoid.

**Change:** `TwrResult` gains `annualized_pct: float | None`. `TwrCalculator` computes it from the same cumulative return and elapsed-days figure it already has once the sub-period linking is done — `(1 + twr_pct/100) ** (365 / elapsed_days) - 1`, `None` whenever `twr_pct` itself is `None`. `sensor.<portfolio>_time_weighted_return` gains an `annualized_pct` attribute. `docs/ENTITY_CONTRACTS.md`'s existing entry for that entity gets one line added, not a new entry.

### 3. Drawdown → new calculator, one entity

**Calculator: yes.** A genuinely distinct risk question ("how far below my peak am I, and how far did I ever fall") that nothing existing answers, computed from data already collected (`portfolio.snapshots`, plus the same synthetic "current value at `as_of`" convention `TwrCalculator`/`MwrCalculator` already use).

**Entity: one.** `sensor.<portfolio>_drawdown`.
- State: current drawdown, as a percentage below the running peak (0 or negative; 0 means "at an all-time high right now").
- Attributes: `max_drawdown_pct`, `max_drawdown_peak_date`, `max_drawdown_trough_date`, `status` (same four-way `"ok"`/`"no_data"`/`"insufficient_data"`/`"not_computable"` pattern every prior return-metric entity uses).
- Unit: `%`. State class: `measurement`.

**Helper vs. calculator:** the peak-to-trough scan over the snapshot value series is single-purpose and stays inline in `DrawdownCalculator` — nothing else needs it.

### 4. Volatility → new calculator, one entity, and the one real helper extraction this milestone needs

**Calculator: yes.** Standard deviation of period returns, annualized — a well-defined, independently useful risk metric.

**The one non-trivial design decision in this whole document:** volatility must be computed from the *same* cash-flow-excluded sub-period returns `TwrCalculator` already derives (snapshot-to-snapshot growth with deposits/withdrawals subtracted out) — using raw, flow-polluted period returns would make volatility partly measure deposit timing instead of market risk, which would be a real correctness bug, not a style choice. `TwrCalculator` currently computes that return series as a private implementation detail (the `sub_returns` list, immediately compounded away). Two calculators now need the same series.

**Resolution: extract `engine/period_returns.py`** — a plain function, `compute_period_returns(portfolio, positions, as_of) -> list[tuple[datetime, datetime, float]]` (period start, end, return), containing exactly the boundary-building and sorted merge-pass logic `TwrCalculator` already has. `TwrCalculator` calls it and compounds the results (unchanged behavior, verified by its existing hand-verified test suite continuing to pass unmodified). `VolatilityCalculator` calls the same function and computes `stdev` × an annualization factor derived from the average period length.

This is **not a new architectural pattern** — it's the same "shared pure function in `engine/`, called by more than one calculator" shape `external_cash_flows.py` already established for `MwrCalculator`/`TwrCalculator`. No calculator calls another calculator here; both call a shared function. That distinction is why this doesn't need a new ADR (see below).

**Entity: one.** `sensor.<portfolio>_volatility`.
- State: annualized volatility (%).
- Attributes: `period_volatility_pct` (unannualized), `periods_used`, `status`.
- Unit: `%`. State class: `measurement`.

### 5. Position analytics → new calculator, one entity

**Calculator: yes.** Purely derived from `positions` (already available every run, no snapshot/transaction dependency) — the simplest of the five candidates.

**Entity: one**, not three or four. `sensor.<portfolio>_concentration`.
- State: the largest single position's share of total portfolio value (%) — the most directly actionable "how concentrated am I" number.
- Attributes: `largest_position` (`symbol`, `pct_of_portfolio`), `largest_winner` (`symbol`, `gain_pct`), `largest_loser` (`symbol`, `gain_pct`), `top_5` (list of `{symbol, pct_of_portfolio}`).
- Unit: `%`. State class: `measurement`.

Rejected: a Herfindahl-Hirschman-style concentration index as the state instead of "largest position %." It's a more statistically rigorous concentration measure, but it's not a number anyone can look at and immediately understand without an explanation — "largest position %" clears the "answers a concrete question in an obvious way" bar the advisory sets, HHI doesn't. Not introduced anywhere, including diagnostics — it would be an implementation detail with no consumer.

## Deferred, not built this milestone

### Portfolio Health — deferred to a later milestone

The advisory's own design (one entity, detailed attributes, combining reconciliation + staleness + concentration + missing-data signals) is sound, but two things argue for deferring it specifically, not just "eventually":

1. **It has nothing to consume yet that isn't already visible.** Reconciliation status is already its own entity. Missing FX rates and missing quotes are already in the `positions` entity's attributes and in diagnostics. Concentration will exist after this milestone. A "health" rollup's entire value is in the aggregation — and aggregating well is easier to get right once every input it aggregates has been live and validated for a while, rather than being designed in the same pass that creates one of its own inputs (concentration).
2. **A real architectural question hides inside it that the other four candidates don't raise.** `Calculator.calculate(portfolio, positions)` doesn't receive other calculators' outputs, and it doesn't receive `update_logic.py`-level data (`fx_rates_missing`, `symbols_missing_quotes` — those are computed and attached outside `engine.run()` entirely, per Milestone 3's design). A health calculator that wants to fold in missing-FX/missing-quote signals needs either (a) a merge step in `update_logic.py`/`sensor_mapping.py` combining engine-level and fetch-level signals for one entity, or (b) staying scoped to only what the engine itself can see (reconciliation + staleness + concentration, composed by directly calling `ReconciliationCalculator`/`PositionAnalyticsCalculator` internally — legitimate plain Python composition, no engine change needed, but a pattern this project hasn't used yet). Neither choice is settled by anything decided so far, and picking one under this milestone's "keep it small" pressure risks a worse decision than making it deliberately, on its own, once.

Recommendation: revisit as its own small milestone once Dividend/Drawdown/Volatility/Concentration have shipped and had at least one round of real use.

### Sharpe ratio, benchmark comparison — deferred, out of scope by the advisory's own rule

Both need data this system doesn't currently have any source for: Sharpe needs a risk-free rate, benchmark comparison needs a benchmark's own price history. Fetching either is a new category of data collection, which the advisory explicitly rules out ("avoid collecting new categories of data," "do not introduce... additional providers"). Not a hard "never" — a future milestone could add a `BenchmarkProvider` deliberately — but it's not this one, and doesn't need a placeholder now.

## What's diagnostics-only (nowhere else)

Nothing new needs a diagnostics-only home this milestone — every output above already has a natural entity or attribute location. `diagnostics.py` gets the same compact-summary treatment as every prior milestone's additions (a `dividends`/`drawdown`/`volatility`/`concentration` block each, mirroring the existing `reconciliation`/`mwr`/`twr` blocks) — troubleshooting-tier, not a new design decision, per the existing carve-out in `ENTITY_API_POLICY.md`.

One explicit exclusion: `VolatilityCalculator`'s raw per-period return sample (the list `compute_period_returns` produces) is never exposed anywhere, entity or diagnostics — it's exactly the "internal implementation detail" the advisory says not to surface, and at potentially hundreds of data points it would also just be noise in a diagnostics dump.

## Net effect

| | Before M7 | After M7 |
|---|---|---|
| Calculators | 7 | 11 (+ `DividendCalculator`, `DrawdownCalculator`, `VolatilityCalculator`, `PositionAnalyticsCalculator`) |
| Shared `engine/` helper modules | `transaction_replay.py`, `xirr.py`, `external_cash_flows.py`, `snapshot_policy.py` | + `period_returns.py` |
| Entities | 10 | 14 (+ `dividend_income`, `drawdown`, `volatility`, `concentration`) + 1 existing entity (`time_weighted_return`) gains an attribute |
| New ADRs | — | 0 (see below) |

## Why no new ADR

Per the advisory's own rule — only when there's a genuine decision with meaningful alternatives, not for straightforward feature additions. Checked against everything above:

- Four new calculators are the same shape as the existing seven — no new pattern.
- `period_returns.py` is the same "shared pure function, multiple calculators call it" shape `external_cash_flows.py` already established — no new pattern.
- CAGR-as-attribute is a data-shape decision (documented inline in `TwrResult`'s docstring and this document), not an architectural one.
- The one place a genuine architectural fork exists — how a future health rollup would access other calculators' and `update_logic.py`'s outputs — is exactly what's being deferred, specifically *because* it deserves its own decision rather than being settled as a side effect of this milestone.

## Testing plan (same categories, same discipline, nothing new)

Each of the four new calculators, in order (independent, so any order works, but doing the one with the shared helper extraction — Drawdown, then Volatility — back to back keeps `period_returns.py`'s two consumers close together in review):

1. Engine unit tests per calculator: hand-verified numeric examples (same standard `test_xirr.py`/`test_twr_calculator.py` set) plus every `status` branch (`no_data`/`insufficient_data`/`not_computable` where applicable).
2. `period_returns.py` gets its own direct unit tests (the extraction is a refactor of tested code — `TwrCalculator`'s existing test suite passing unmodified is the correctness gate for the refactor itself; `period_returns.py`'s own tests cover it as a standalone unit for its second consumer, `VolatilityCalculator`).
3. Pure-logic integration tests (`tests_integration/test_sensor_mapping.py`) for the four new mapping-function pairs.
4. Real-HA-harness tests per entity: registration/device grouping, `unknown` state on insufficient data, `ok` computation, diagnostics block — same four-test shape every prior return-metric entity has used since Milestone 5.
5. Benchmark: extend `scripts/benchmark.py`'s calculator registration to all 11; no new benchmark *dimension* needed unless implementation reveals one (the two existing dimensions — holdings count, snapshot-history length — already stress everything these four calculators touch).

## Acceptance criteria

- [ ] `DividendCalculator`, `DrawdownCalculator`, `VolatilityCalculator`, `PositionAnalyticsCalculator` implemented and registered (11 calculators total)
- [ ] `period_returns.py` extracted; `TwrCalculator`'s full existing test suite passes unmodified against the refactored implementation
- [ ] `TwrResult.annualized_pct` added; existing TWR entity/tests updated, no new entity
- [ ] Four new entities implemented with `docs/ENTITY_CONTRACTS.md` entries, each following the "one entity, rich attributes" shape decided above — no additional entities beyond the four
- [ ] `PortfolioHealthCalculator`, Sharpe ratio, and benchmark comparison explicitly not implemented this milestone
- [ ] All three test categories updated per the plan above; full suite passing
- [ ] `BENCHMARKS.md` re-run and updated
- [ ] `CHANGELOG.md` updated
- [ ] No new ADR (or, if implementation surfaces a real fork this design didn't anticipate, write one then — not preemptively)
