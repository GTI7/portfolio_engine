# Milestone 3: Currency Support

**Status:** Complete for the agreed scope (Currency Provider, exchange-rate service, multi-currency calculations, base-currency conversion, validation, testing). No other functionality added — no new providers, dividends, goals, or multi-portfolio support, per the milestone's explicit boundary.

## What's included

- **`providers/currency_base.py`** — `CurrencyProvider` interface. `async_get_rates(base, targets) -> dict[currency, rate]`, where `rate` converts an amount in that currency to `base` by multiplication. Separate from `PriceProvider` per ADR-0002 (already-decided architecture — no new ADR needed for this milestone, just implementing what was already specified).
- **`providers/yahoo_finance_currency.py`** — `YahooFinanceCurrencyProvider`, reusing the same batched Yahoo Finance quote endpoint as `YahooFinanceProvider`, via FX-pair symbols (`<currency><base>=X`). One HTTP call for any number of currencies needed, same scalability property as the price provider.
- **`engine/portfolio_engine.py`** — `build_positions()`/`run()` now take an optional `fx_rates` parameter and do all currency conversion in one place. `Position` gained `cost_basis_base` and `fx_rate`; `unrealized_gain`/`gain_pct` are now computed on base-currency figures. Calculators (`PortfolioCalculator`, `AllocationCalculator`, `PerformanceCalculator`) were **not** changed to do FX math — they already consumed `market_value_base`/`cost_basis_base`, so multi-currency support required zero calculator-level changes beyond `PortfolioCalculator` losing its now-redundant `_convert()` stub.
- **`update_logic.py`** — fetches FX rates only for currencies actually present among the portfolio's holdings and differing from its base currency. A single-currency portfolio never calls the currency provider at all (confirmed by test, not just asserted).
- **`fx_rates_missing`** — surfaced in the `positions` entity's attributes and in `diagnostics.py`. A rate the provider couldn't supply falls back to 1.0 (documented best-effort — same behavior as a same-currency holding, so it degrades to "no conversion" rather than crashing) and is visible as missing, not silently wrong.

## Backward compatibility

Every one of the 31 pre-Milestone-3 tests passes unmodified. This wasn't incidental — it's the direct consequence of `fx_rate` defaulting to `1.0` for same-currency holdings and `unrealized_gain`/`gain_pct` being computed from base-currency figures that are numerically identical to the native-currency figures whenever `currency == base_currency`. Single-currency portfolios (the only kind Milestones 1–2 supported) behave exactly as before.

## Testing

71 tests total across the three automated categories (`TESTING.md`), up from 58 before this milestone:

| Category | New tests | What they cover |
|---|---|---|
| Engine unit (`tests/`) | 11 | `YahooFinanceCurrencyProvider` batching/fallback/empty-target behavior (4); multi-currency `PortfolioCalculator`/`AllocationCalculator` (2); end-to-end `PortfolioEngine.run()` with FX rates, including a missing-rate fallback case (3); pre-existing calculator tests updated for the `Position` shape change (not new tests, but touched) |
| Pure-logic integration (`tests_integration/`) | 3 | Single-currency portfolios never call the currency provider; multi-currency portfolios fetch and apply rates correctly; a missing rate is reported in `fx_rates_missing`, not silently dropped |
| Real HA harness (`tests_ha/`) | 2 | A full config-entry setup with a real EUR-base / USD-holding portfolio produces correctly-converted entity states; a missing exchange rate doesn't fail setup, surfaces in the positions attributes instead |

## Validation checklist

- [x] `pytest tests/` — 39/39 (31 pre-existing + 8 new/updated for multi-currency)
- [x] `pytest tests_integration/` — 12/12
- [x] `pytest tests_ha/` (real HA harness) — 20/20, including both new multi-currency tests
- [x] `ruff check .` / `mypy` — clean
- [x] `BENCHMARKS.md` re-run at engine v0.3.0 — same linear scaling, no measurable regression from the added FX lookup
- [x] `docs/ENTITY_CONTRACTS.md` updated for the `positions` entity's new `fx_rate`/`fx_rates_missing` attribute additions (additive, not a contract change — per `ENTITY_API_POLICY.md`'s carve-out for that entity's attribute shape)
- [x] `CHANGELOG.md` updated

## What was deliberately not touched

No new ADRs (this milestone implements architecture already specified in ADR-0002 and the architecture doc's Section 3, it doesn't introduce new architectural decisions). No changes to `docs/COMPATIBILITY_POLICY.md` (nothing HA-version-specific changed) or `docs/ENTITY_API_POLICY.md` beyond the one attribute-shape note already covered by its existing carve-out rule. No new calculators, providers beyond currency, dividends, goals, or multi-portfolio work — all explicitly out of scope per the milestone's own boundary.
