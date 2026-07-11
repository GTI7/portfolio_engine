# Entity Contracts

Every entity this integration exposes is documented here from the moment it ships, per the governance principle established at the end of Milestone 2.5: **an entity is a documented contract, not just a working sensor.** `docs/ENTITY_API_POLICY.md` governs how contracts may change once published (additive-preferred, breaking changes require release notes); this document is where each contract actually lives.

**Process going forward:** a new entity is not considered "shipped" until it has an entry here. Add the entry in the same PR/commit that adds the entity — not as a follow-up.

## Template

Copy this for every new entity:

```markdown
### `sensor.<domain>_<name>`

- **Purpose:** What question does this entity answer, in one sentence.
- **State meaning:** Exactly what the numeric/string state represents — units of measurement handled separately below, this is about semantic meaning (e.g. "positions only, cash excluded" vs. "includes cash").
- **Unit of measurement:** e.g. base currency code, `%`, count.
- **State class:** `total`, `measurement`, `total_increasing`, or none — and why that one (affects how HA's statistics engine treats it; see `docs/ENTITY_API_POLICY.md` rule 4).
- **Device class:** e.g. `monetary`, or none.
- **Intended automation use:** Concrete example(s) of an automation that would reasonably trigger on or reference this entity.
- **Intended dashboard use:** Where this shows up (KPI tile, chart series, table attribute source, etc.).
- **Attributes:** Any `extra_state_attributes`, with the same level of detail as the state itself if non-trivial.
- **Stability notes:** Anything specific to this entity beyond the general policy (e.g. "the `positions` attribute's per-item shape is allowed to grow").
```

---

## Shipped entities

### `sensor.<portfolio>_value`

- **Purpose:** Answers "what is my portfolio worth right now, all-in."
- **State meaning:** Total positions market value (base currency) **plus** cash balance. Not invested capital, not a return figure — a point-in-time worth.
- **Unit of measurement:** Portfolio's base currency code (e.g. `USD`, `EUR`), read from the portfolio config.
- **State class:** `total` — appropriate for an absolute point-in-time balance (not a rate, not monotonically increasing), which is what makes HA's long-term statistics show it correctly as a value-over-time series rather than trying to sum it.
- **Device class:** `monetary`.
- **Intended automation use:** Milestone-reached notifications (`numeric_state` trigger `above: <target>`); daily/weekly summary automations reading the current value.
- **Intended dashboard use:** The headline KPI tile on an Overview-style dashboard; the primary series on a "portfolio value over time" chart (via Recorder statistics).
- **Attributes:** None beyond the standard HA ones.
- **Stability notes:** If a future milestone wants a "positions-only, cash-excluded" total-value variant, that's a **new** entity (e.g. `sensor.<portfolio>_positions_value`), not a redefinition of this one — see `ENTITY_API_POLICY.md` rule 3.

### `sensor.<portfolio>_total_invested`

- **Purpose:** Answers "how much capital have I actually put into positions."
- **State meaning:** Sum of cost basis (`shares × avg_price`) across all positions, in base currency. Cash is never counted as "invested."
- **Unit of measurement:** Portfolio's base currency code.
- **State class:** `total`.
- **Device class:** `monetary`.
- **Intended automation use:** Rarely triggered on directly; mostly a reference value pulled into notification message templates alongside `portfolio_value`/`portfolio_total_profit`.
- **Intended dashboard use:** Secondary KPI tile; denominator context next to ROI.
- **Attributes:** None.
- **Stability notes:** Once multi-currency support (Milestone 3) lands, this value's *calculation* changes (real FX conversion instead of same-currency assumption) but its *meaning* doesn't — not a breaking change per `ENTITY_API_POLICY.md` rule 3, since "what the number represents" is unchanged, only its accuracy improves.

### `sensor.<portfolio>_total_profit`

- **Purpose:** Answers "how much have my positions gained or lost, in absolute terms."
- **State meaning:** `portfolio_value`'s positions component minus `total_invested` — unrealized gain/loss. Cash contributes nothing here (it can't gain or lose).
- **Unit of measurement:** Portfolio's base currency code.
- **State class:** `total`.
- **Device class:** `monetary`.
- **Intended automation use:** Threshold notifications ("profit crossed €X"), paired with `portfolio_roi` for percentage-based alternatives to the same underlying event.
- **Intended dashboard use:** KPI tile, typically conditionally colored (green/red) based on sign.
- **Attributes:** None.
- **Stability notes:** "Unrealized" specifically — once realized gains (from a transaction log, a later milestone) exist as a concept, that's a new entity, not a change to this one's meaning.

### `sensor.<portfolio>_roi`

- **Purpose:** Answers "what's my percentage return on invested capital."
- **State meaning:** `total_profit / total_invested * 100`. Deliberately invested-capital-basis, not total-value-basis — cash sitting uninvested doesn't dilute or inflate this number.
- **Unit of measurement:** `%`.
- **State class:** `measurement` (a ratio/percentage, not an accumulating total — `total` would be semantically wrong here).
- **Device class:** None (no `PERCENTAGE`-specific monetary device class applies).
- **Intended automation use:** "Notify when ROI exceeds/drops below X%" threshold automations.
- **Intended dashboard use:** KPI tile, often paired with `total_profit` as the percentage/absolute pair for the same underlying gain.
- **Attributes:** None.
- **Stability notes:** See `ENTITY_API_POLICY.md` rule 3's explicit example — redefining this to a total-value basis would be a breaking meaning change; a total-value-basis version, if ever wanted, is a new entity.

### `sensor.<portfolio>_cash_balance`

- **Purpose:** Answers "how much uninvested cash do I have in this portfolio."
- **State meaning:** `Portfolio.cash_balance` directly, in base currency — a first-class model field (ADR-0008), not derived from positions.
- **Unit of measurement:** Portfolio's base currency code.
- **State class:** `total`.
- **Device class:** `monetary`.
- **Intended automation use:** "Notify when cash balance exceeds X" (e.g. as a prompt to deploy idle cash) — a natural future use once such an automation example is added to `automations.yaml` in a later milestone.
- **Intended dashboard use:** KPI tile; also the source for the "Cash" slice on an allocation donut chart (via the engine's `AllocationCalculator` output, once an allocation entity ships).
- **Attributes:** None.
- **Stability notes:** None beyond the general policy.

### `sensor.<portfolio>_positions`

- **Purpose:** Answers "what do I actually hold, in detail" — the one entity that exposes the full holdings table.
- **State meaning:** Count of positions (an integer, so the entity is still meaningful if ever shown bare without its attributes).
- **Unit of measurement:** `positions` (a count unit, not a real physical/monetary unit).
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** Not typically automation-triggering itself; occasionally useful as a `template` condition source (e.g. "if positions count changed, something was added/removed").
- **Intended dashboard use:** The data source for the Holdings table (`flex-table-card` or similar reading the `positions` attribute) and per-asset detail views.
- **Attributes:** `positions` (list of dicts — full `Position` objects including nested `Holding` and `Quote`, and, as of Milestone 3, `fx_rate` per position), `portfolio_id`, `portfolio_name`, `base_currency`, `symbols_missing_quotes`, `fx_rates_missing` (currencies whose exchange rate couldn't be fetched this cycle, added in Milestone 3 — see `providers/currency_base.py`).
- **Stability notes:** Per `ENTITY_API_POLICY.md`'s explicit carve-out — the *per-item shape* inside the `positions` list attribute is allowed to grow additively (e.g. adding `sector`/`region` fields later) without that being treated as a breaking change to this entity. Removing or renaming a field within that shape *is* still breaking, by the same logic as any other meaning change.

### `sensor.<portfolio>_transaction_count`

- **Purpose:** Answers "how many transactions are on record for this portfolio, and what happened most recently" — added in Milestone 4 (MILESTONE_4_SPEC.md Section 9).
- **State meaning:** Count of `Transaction` entries in `portfolio.transactions` (the full log, not just recent ones).
- **Unit of measurement:** `transactions` (a count unit).
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** State-change trigger for "notify me when a new transaction is logged" (the count changing is the signal — no dedicated "last transaction" entity was added separately, since the `recent` attribute already covers that need without growing the entity surface further).
- **Intended dashboard use:** A small recent-activity table/list on a Transactions dashboard view, reading the `recent` attribute directly.
- **Attributes:** `recent` — the 10 most recent transactions (newest first), each with `id`, `portfolio_id`, `type` (string, e.g. `"buy"`), `date` (ISO 8601 string), `currency`, `amount`, `symbol`, `shares`, `price`, `notes`.
- **Stability notes:** The `recent` limit (10) and per-item shape are implementation details of this entity, not separately versioned — a limit change would be a behavior change worth a release note per `docs/COMPATIBILITY_POLICY.md`, but not a breaking *contract* change the way removing a field from `recent` would be.

### `sensor.<portfolio>_reconciliation`

- **Purpose:** Answers "does my declared portfolio state (`holdings.yaml`/`cash_balance`) match what the transaction log implies" — a data-integrity check, not a portfolio metric. Added in Milestone 4; see `docs/adr/0010-transaction-log-as-validation-layer.md` for why this is validation-only and doesn't make the transaction log authoritative.
- **State meaning:** One of three strings — `"ok"` (compared and matched, within tolerance), `"discrepancy"` (compared and found a mismatch), or `"no_data"` (no transactions logged for this portfolio, so nothing was compared). `"no_data"` is deliberately distinct from `"ok"` — the absence of a check is not the same claim as a passed check.
- **Unit of measurement:** None (string state).
- **State class:** None (not numeric — a status, not a measurement).
- **Device class:** None.
- **Intended automation use:** "Notify me if reconciliation status becomes `discrepancy`" — a genuinely new capability this milestone provides: catching a typo in `holdings.yaml`, a forgotten manual update after a real-world trade, or an incomplete transaction log.
- **Intended dashboard use:** A status indicator (e.g. green for `ok`, red for `discrepancy`, grey/neutral for `no_data`) plus a detail table from the `discrepancies` attribute when non-empty.
- **Attributes:** `discrepancies` (list of `{symbol, field, declared, reconstructed, difference}` — `field` is one of `"shares"`, `"avg_price"`, `"cash_balance"`; `symbol` is `null` for the cash-balance discrepancy), `transactions_considered` (count).
- **Stability notes:** The tolerance threshold (0.01, `engine/calculators/reconciliation_calculator.py`'s `TOLERANCE`) is an implementation detail, not part of this entity's contract — it exists to filter float-rounding noise, not to define the entity's meaning. A future milestone adding new comparable fields (once the domain model gains sector/region, say) would add new `field` values to `discrepancies`, additive per the same carve-out logic as the `positions` entity above.

### `sensor.<portfolio>_money_weighted_return`

- **Purpose:** Answers "what annualized return has my invested capital actually earned, accounting for the timing and size of every deposit and withdrawal" — money-weighted return (XIRR). Added in Milestone 5; see `docs/adr/0011-mwr-external-cash-flow-classification.md` for exactly which transaction types count as external cash flows and why.
- **State meaning:** The XIRR rate as a percentage (e.g. `12.5` means 12.5% annualized), computed from `DEPOSIT`/`WITHDRAWAL`/`TRANSFER_IN`/`TRANSFER_OUT` transactions plus the portfolio's current total value as a terminal cash flow. `BUY`/`SELL`/`DIVIDEND`/`FEE` never contribute — they're internal to the portfolio and already reflected in the terminal value. State is `None` (HA renders `unknown`) whenever `MwrResult.status != "ok"` — the reason is in the `status` attribute, not encoded in the state itself.
- **Unit of measurement:** `%`.
- **State class:** `measurement` (a rate, not an accumulating total).
- **Device class:** None.
- **Intended automation use:** "Notify me if money-weighted return drops below X%" threshold automations; also useful as a `template` condition checking `status == "ok"` before referencing the numeric state, since `unknown` is a normal, expected value for portfolios without enough transaction history yet.
- **Intended dashboard use:** A KPI tile alongside `portfolio_roi` — ROI is a simple, timing-naive percentage on invested capital; MWR is the more sophisticated, timing-aware companion figure for anyone who wants it. Dashboards should handle the `unknown` state gracefully (e.g. "Not enough data yet" instead of blank).
- **Attributes:** `status` (`"ok"` | `"no_data"` | `"insufficient_data"` | `"not_computable"` — see `engine/models.py`'s `MwrResult` docstring for the distinction between each), `cash_flow_count`, `as_of` (ISO 8601 string — the terminal-value timestamp used in the calculation, i.e. roughly "now" at the last coordinator refresh).
- **Stability notes:** The XIRR solver's internal method (Newton-Raphson vs. bisection fallback, `engine/xirr.py`) and its tolerance/iteration-limit constants are implementation details, not part of this entity's contract — only the final `rate_pct` value and the `status`/`cash_flow_count`/`as_of` attributes are. If cash-flow classification (ADR-0011's table) ever changes — e.g. a future milestone reconsiders whether `DIVIDEND` should count — that changes this entity's *meaning*, and would need release notes per `docs/COMPATIBILITY_POLICY.md`, the same as any other meaning change.

### `sensor.<portfolio>_time_weighted_return`

- **Purpose:** Answers "what return has this portfolio actually earned as an investment, independent of when and how much I deposited or withdrew" — time-weighted return. Added in Milestone 6, alongside the snapshot mechanism it depends on (`docs/adr/0012-snapshot-repository-and-store-backed-persistence.md`).
- **State meaning:** The cumulative (holding-period, NOT annualized) time-weighted return as a percentage, computed by linking sub-period returns between consecutive `Snapshot`s (plus a synthetic final period to the current live value). Deposits/withdrawals/transfers are excluded from the return itself — see `engine/calculators/twr_calculator.py`'s docstring for the exact method and its known approximation bound (accuracy depends on snapshot frequency, since valuations are only available once per calendar date under this milestone's collection policy). State is `None` (HA renders `unknown`) whenever `TwrResult.status != "ok"` — most commonly because there's no snapshot history yet (a brand-new portfolio) or not enough elapsed time since the first one.
- **Unit of measurement:** `%`.
- **State class:** `measurement` (a rate, not an accumulating total — same reasoning as `portfolio_roi`).
- **Device class:** None.
- **Intended automation use:** Same shape as `portfolio_money_weighted_return` — threshold notifications, and a `template` condition checking `status == "ok"` before referencing the numeric state, since `unknown` is the expected state for the first several days of a newly tracked portfolio (no snapshot history yet to form a period from).
- **Intended dashboard use:** A KPI tile alongside `portfolio_roi` and `portfolio_money_weighted_return` — three different, deliberately distinct answers to "how has this portfolio done": ROI (simple, invested-capital basis), MWR (timing-and-size-of-cash-flow-sensitive), TWR (timing-and-size-of-cash-flow-*insensitive*, the "pure investment skill" figure). Dashboards should handle the `unknown` state gracefully, same as the MWR entity.
- **Attributes:** `status` (`"ok"` | `"no_data"` | `"insufficient_data"` | `"not_computable"` — see `engine/models.py`'s `TwrResult` docstring), `periods_used` (how many snapshot-to-snapshot sub-periods were linked), `as_of` (ISO 8601 string — the terminal-value timestamp, same convention as MWR's), `annualized_pct` (Milestone 7 — CAGR, the same cumulative return expressed as a compound annual rate over the elapsed period; `None` under the same conditions `twr_pct` is `None`).
- **Stability notes:** `twr_pct` is explicitly cumulative, not annualized (Milestone 7's `annualized_pct` — a genuinely additive attribute, not a redefinition of `twr_pct`'s existing meaning). The sub-period-linking method's specific handling of cash flows occurring *within* a snapshot-to-snapshot window (currently: attributed to the period's end) is an implementation detail of the approximation, not part of this entity's contract — a future milestone with more frequent snapshots would change the *precision* of this number without changing what it means.

### `sensor.<portfolio>_dividend_income`

- **Purpose:** Answers "how much dividend income has this portfolio generated recently" — added in Milestone 7. See `MILESTONE_7_DESIGN.md`'s dividend-analytics section for why this is one entity, not four.
- **State meaning:** Rolling 12-month dividend income, summed from `DIVIDEND` transactions dated within the trailing 365 days of `as_of` (no new transaction type — Milestone 4's existing `DIVIDEND` type is the sole data source). `None` (`"unknown"`) whenever no dividend has ever been recorded.
- **Unit of measurement:** Portfolio's base currency code.
- **State class:** None (unset). **Corrected in Milestone 9** — originally shipped as `measurement`, reasoned as "a rolling window, not a monotonic total." That's true of the data, but `SensorDeviceClass.MONETARY` only permits `state_class` of `None` or `total`, never `measurement` — HA silently drops an invalid combination at runtime, breaking Recorder statistics for the entity rather than merely logging a cosmetic warning. `total` doesn't fit either (it implies monotonic accumulation, which a rolling window isn't), so `None` is the honest choice — this entity does not get Recorder long-term statistics, by design, not by oversight.
- **Device class:** `monetary`.
- **Intended automation use:** "Notify me if dividend income drops materially" (a `numeric_state` `below` trigger) — a genuinely new signal this entity provides.
- **Intended dashboard use:** A KPI tile on an income-focused view, alongside `dividend_yield_pct` from its attributes.
- **Attributes:** `status` (`"ok"` | `"no_data"`), `lifetime` (all-time total), `current_year` (this calendar year to date), `dividend_yield_pct` (rolling-12-month income ÷ total invested capital — `None` if there's no invested capital to divide by), `average_monthly_dividend`, `as_of`.
- **Stability notes:** The rolling window is fixed at 365 days and the yield denominator is invested capital (cost basis), not current market value — both are documented choices, not implementation accidents; changing either would be a meaning change requiring release notes, not a routine tweak.

### `sensor.<portfolio>_drawdown`

- **Purpose:** Answers "how far below my portfolio's peak value am I right now, and how far did it ever fall" — added in Milestone 7.
- **State meaning:** Current drawdown as a percentage below the running peak (0 or negative; `0` means "at an all-time high right now"). Unlike the return-metric entities (MWR/TWR/Volatility), this is computed from the portfolio's *raw* value trajectory — deposits and withdrawals are allowed to move it, since a real investor watching their balance would see exactly that movement (see `DrawdownCalculator`'s docstring for why this is the one Milestone 7 calculator that deliberately does *not* use the cash-flow-excluded return series).
- **Unit of measurement:** `%`.
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** "Notify me if drawdown exceeds X%" — a risk-awareness alert.
- **Intended dashboard use:** A KPI tile, often paired with `maximum_drawdown_pct` from attributes to show "how bad is it right now vs. how bad has it ever been."
- **Attributes:** `status` (`"ok"` | `"no_data"` — never `"insufficient_data"`; a single snapshot is already enough to compute a trivial "at peak" drawdown, see `DrawdownResult`'s docstring), `maximum_drawdown_pct`, `peak_value`, `peak_date` (ISO 8601 string), `recovery_status` (`"at_peak"` | `"recovering"` | `"in_drawdown"`), `as_of`.
- **Stability notes:** `recovery_status`'s three values and the tolerance used to decide "at peak" (`AT_PEAK_TOLERANCE_PCT` in `engine/calculators/drawdown_calculator.py`) are implementation details of how the state is classified, not separately part of this entity's contract beyond the three string values themselves being stable.

### `sensor.<portfolio>_volatility`

- **Purpose:** Answers "how much does this portfolio's value swing around, independent of deposits and withdrawals" — a standard risk metric, added in Milestone 7.
- **State meaning:** Annualized standard deviation of the same cash-flow-excluded sub-period returns `TwrCalculator` uses (`engine/period_returns.py`, shared between the two — see `MILESTONE_7_DESIGN.md`'s helper-extraction section for why sharing this series specifically is a correctness requirement, not a style choice). `None` (`"unknown"`) whenever fewer than two periods are available.
- **Unit of measurement:** `%`.
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** "Notify me if volatility rises above X%" — a risk-awareness alert, complementary to `drawdown`'s "how bad has it gotten" framing with "how much does it move around" instead.
- **Intended dashboard use:** A KPI tile, typically alongside `drawdown` and `time_weighted_return` on a risk/performance-focused view.
- **Attributes:** `status` (`"ok"` | `"no_data"` | `"insufficient_data"` | `"not_computable"` — inherited from `engine/period_returns.py`'s status vocabulary), `daily_volatility_pct` (unannualized, despite the name — matches the attribute name requested in the implementation brief; it's the raw per-period standard deviation, not literally daily unless snapshots happen to be exactly daily), `observation_period_days`, `sample_count`, `as_of`.
- **Stability notes:** The annualization scaling factor (`sqrt(365 / average_period_length_days)`) is an implementation detail — it adapts automatically to whatever snapshot cadence actually occurred, so this entity's meaning ("annualized volatility") stays stable even if the underlying snapshot frequency changes.

### `sensor.<portfolio>_concentration`

- **Purpose:** Answers "how concentrated is my portfolio in a single position, and which positions are driving my results" — added in Milestone 7. See `MILESTONE_7_DESIGN.md`'s position-analytics section for why this is one entity with several attributes rather than three or four entities.
- **State meaning:** The largest single position's share of total portfolio value, as a percentage. `None` (`"unknown"`) when there are no positions or total portfolio value is zero.
- **Unit of measurement:** `%`.
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** "Notify me if my largest position exceeds X% of my portfolio" — a concentration-risk alert.
- **Intended dashboard use:** A KPI tile plus a detail view built from `largest_winner`/`largest_loser`/top-5 breakdown in attributes.
- **Attributes:** `status` (`"ok"` | `"no_data"`), `largest_position` (`{symbol, pct_of_portfolio, gain_pct}`), `largest_winner`, `largest_loser` (same shape, by `gain_pct`), `top5_concentration_pct`, `diversification_score` (0–100, higher is more diversified), `herfindahl_index` (the standard 0–1 concentration index the diversification score is derived from — both are exposed since they read in opposite "bigger is better" directions for different audiences, see `PositionAnalyticsCalculator`'s docstring), `holding_count`.
- **Stability notes:** `top5_concentration_pct` is always "top 5 or all holdings, whichever is fewer" — with fewer than 5 positions it equals 100%. `diversification_score`'s exact formula (`(1 - HHI) * 100`) is implementation detail; only its 0–100, higher-is-better direction is part of the contract.

### `sensor.<portfolio>_last_import`

- **Purpose:** Answers "how did my last broker import go, and when did it happen" — added in Milestone 9 alongside `portfolio_engine.import_transactions`. (This entry was missing from this document until Milestone 13 Phase 2's design review caught the gap — the entity itself has been unchanged since Milestone 9; this is a documentation-only correction, not a new or modified entity.)
- **State meaning:** The last import's imported-transaction count (an integer). `None` (`"unknown"`) whenever no import has ever been run for this portfolio.
- **Unit of measurement:** `transactions` (a count unit, same convention as `portfolio_transaction_count`).
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** State-change trigger for "notify me after a broker import runs," or a `numeric_state` check on `rejected`/`duplicates` (in attributes) to flag an import that needs review.
- **Intended dashboard use:** A status tile on an Administration/Import view, expanded with the attributes below for the full report summary.
- **Attributes:** When no import has ever run: `{"status": "never_imported"}`. Otherwise: `status` (`"ok"`), `provider`, `as_of` (ISO 8601 string), `transactions_read`, `imported`, `duplicates`, `rejected`, `warnings` (list of strings).
- **Stability notes:** Persisted via `ImportReportStore` (Home Assistant `Store`, keyed by config entry), so the state survives restarts. Milestone 12's `portfolio_engine.apply_import` service clears the underlying stored report once its rows are written to `transactions.yaml` — this entity reverting to `None`/`"unknown"` after a successful `apply_import` call is expected behavior (there is no longer a *pending* report), not a bug; run `import_transactions` again to populate it for the next review cycle.

### `sensor.<portfolio>_day_change`

- **Purpose:** Answers "how has my portfolio moved today" — added in Milestone 13 Phase 2, exposing a calculation (`PerformanceCalculator`) that has existed since Milestone 1 but was never surfaced as an entity until now.
- **State meaning:** Each position's own day-over-day change percentage (from its `Quote.change_pct`), weighted by that position's share of total portfolio value (positions + cash); cash itself contributes a 0% change, diluting the total proportionally to how much of the portfolio is uninvested — matching how an investor would actually experience "how much did I move today" (idle cash doesn't move with the market). Always a concrete number, never `None`/`"unknown"` — `0.0` for a portfolio with no positions, since there's nothing to move.
- **Unit of measurement:** `%`.
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** "Notify me if today's change exceeds/drops below X%" — a same-day volatility alert, distinct from `portfolio_drawdown` (which tracks distance from an all-time peak, not day-over-day movement).
- **Intended dashboard use:** A KPI tile alongside `portfolio_value` on an Overview-style view — "what is it worth" paired with "how did it move today."
- **Attributes:** None. `PerformanceResult` (the underlying calculator output) also defines `weekly_change_pct`/`monthly_change_pct`/`ytd_change_pct`, but these are hardcoded `0.0` stubs in the engine today (see `engine/models.py`'s `PerformanceResult` docstring — pending a real history-based calculation in a future milestone) and are deliberately *not* exposed here: surfacing a constant `0.0` as if it were a real weekly/monthly/YTD figure would mislead a dashboard reader into thinking that data is being tracked when it isn't.
- **Stability notes:** When a future milestone implements real weekly/monthly/YTD calculations, those become **new attributes on this entity** (additive, per `ENTITY_API_POLICY.md`'s preference for additive changes) — not a redefinition of what `day_change_pct`'s own state means, since it will remain "today's change" specifically.

### `sensor.<portfolio>_allocation`

- **Purpose:** Answers "how is my portfolio allocated across asset types" — added in Milestone 13 Phase 2, exposing a calculation (`AllocationCalculator`, `group_by="type"`) that has existed since Milestone 3 but was never surfaced as an entity until now.
- **State meaning:** The largest allocation group's share of total portfolio value (positions + cash), as a percentage. Groups are formed by each holding's `type` field (e.g. `stock`, `etf`, `mutual_fund`, `crypto`) plus a synthetic `Cash` group whenever `cash_balance > 0` (per `docs/adr/0008-cash-as-first-class-domain-concept.md` — cash counts toward the 100% total like any other group, rather than being silently excluded from the denominator). `None` (`"unknown"`) when there are no groups at all (no holdings and no cash).
- **Unit of measurement:** `%`.
- **State class:** `measurement`.
- **Device class:** None.
- **Intended automation use:** "Notify me if my allocation to one asset type exceeds X%" — an asset-allocation-drift alert, distinct from `portfolio_concentration` (which tracks concentration in a single *position*, not an asset *type*).
- **Intended dashboard use:** A KPI tile showing the largest group's share, paired with the `allocation` attribute for a full breakdown table or pie chart across every group.
- **Attributes:** `allocation` (list of `{label, value, pct}` dicts — `label` is the group name, e.g. `"stock"`/`"Cash"`; `value` is that group's total in base currency; `pct` is its share of the portfolio total — already sorted largest-first by the calculator itself), `largest_group` (the top group's `label`, for convenience — `None` if there are no groups), `group_count`.
- **Stability notes:** This entity always groups by `type` — `AllocationCalculator` itself supports grouping by an arbitrary `Holding` field (e.g. a future `currency`-based breakdown), but a different grouping would be a **new entity**, not a redefinition of this one's meaning, per `ENTITY_API_POLICY.md` rule 3. The per-group dict shape inside the `allocation` attribute is allowed to grow additively (e.g. a future `holding_count` per group), matching the same carve-out `sensor.<portfolio>_positions`'s `positions` attribute already has.
