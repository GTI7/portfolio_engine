# Milestone 5: Money-Weighted Return (MWR / XIRR)

**Status:** Complete for the agreed scope. No spec document this time — the scoping message itself was detailed enough to implement directly from, with the same phase discipline (tests gating each step) as Milestone 4.

## What's included

- **`engine/xirr.py`** — pure-numerics XIRR solver. Newton-Raphson first (fast, converges in single digits of iterations for realistic series), falls back to bisection (slower, guaranteed to converge given a valid bracket) if Newton fails, diverges, or hits a zero derivative. No numpy/scipy dependency. Validated against the canonical Excel XIRR reference example (`-10000, 2750, 4250, 3250, 2750` → `37.3362535%`, matched to 6 decimal places) plus several hand-verifiable cases (`1000 → 1100` in exactly one year is exactly 10%, etc.).
- **`MwrCalculator`** (sixth calculator) — builds the external cash-flow series and calls `xirr()`. Which transaction types count, and how, is `docs/adr/0011-mwr-external-cash-flow-classification.md`'s decision: `DEPOSIT`/`WITHDRAWAL` at face value, `TRANSFER_IN`/`TRANSFER_OUT` at `shares * price` (not their literal `Transaction.amount`, which is always `0.0`), `BUY`/`SELL`/`DIVIDEND`/`FEE` excluded entirely — they're internal to the portfolio and already reflected in the terminal value, so including them would double-count.
- **`MwrResult`** — a three-way `status` (`"ok"` / `"no_data"` / `"insufficient_data"` / `"not_computable"`), same pattern as Milestone 4's `ReconciliationResult`, for the same reason: "not computable" and "computed and it's 0%" are different claims.
- **`sensor.<portfolio>_money_weighted_return`** — the ninth entity, full contract in `docs/ENTITY_CONTRACTS.md`. Reports `None` (HA `unknown`) when status isn't `"ok"`, with the reason in the `status` attribute — same convention as the reconciliation entity.
- **ADR-0011** — the one new ADR this milestone needed. Cash-flow classification is a genuine fork with real alternatives (should dividends count? should transfers be valued at their literal zero `amount` or their economic value?), not an extension of already-decided architecture, so it earns a written decision.

## Why no separate spec document

Milestone 4 went spec-first because the domain questions (immutability, IDs, cost-basis method, storage format) needed resolving before any code made sense. This milestone's scoping message already answered the equivalent questions directly (which algorithm, which fallback, which edge cases, which entity) at a level of detail that made a second round-trip through a formal spec document pure overhead rather than added clarity — so I built from it directly, keeping the same discipline (small phases, tests before moving on) that made Milestone 4 work well.

## Two things worth flagging

1. **Translations were added in the same step as the entity this time**, not as an afterthought. Milestone 4 shipped two entities that briefly resolved to friendly name "None" because the translation strings were missing — caught by the real-HA-harness tests, but avoidable. This milestone's `strings.json`/`translations/en.json` entry went in immediately after `sensor.py`'s class, and all 5 real-HA-harness tests for the new entity passed on the first run.
2. **A noisy benchmark run was caught before being recorded, not published as the baseline.** An initial run showed 500 holdings taking barely more time than 1000 — algorithmically implausible. Re-running at double the repeat count produced clean linear numbers, confirming it was sandbox CPU-contention noise. `BENCHMARKS.md` documents both the noise and the clean re-run, rather than silently swapping in a better-looking number without explanation.

## Test count by category

| Category | New tests | Cumulative |
|---|---|---|
| Engine unit (`tests/`) | 24 (13 XIRR + 11 MwrCalculator) | 160 |
| Pure-logic integration (`tests_integration/`) | 3 | 20 |
| Real HA harness (`tests_ha/`) | 5 | 30 |

**210 tests total**, up from 178 at Milestone 4.

## Validation checklist

- [x] `MwrCalculator` implemented, registered as the sixth calculator
- [x] XIRR solver: Newton-Raphson with bisection fallback, both exercised by tests (`test_bisection_fallback_handles_a_case_newton_struggles_with`)
- [x] Terminal cash flow uses current portfolio value (positions + cash), dated `as_of` (injectable for tests, real "now" by default)
- [x] Edge cases handled: no cash flows (`no_data`), only internal transactions (`no_data`), all flows same date (`insufficient_data`), no sign change (`insufficient_data`), non-convergence (`not_computable`) — each has a dedicated test
- [x] `sensor.<portfolio>_money_weighted_return` entity added, contract written, real-HA-harness tests including the `unknown`-state cases
- [x] Comprehensive unit tests with known reference datasets — the canonical Excel XIRR example plus hand-verifiable simple cases
- [x] HA integration tests: entity registration/device grouping, `ok` computation, `no_data` state, `not_computable`-adjacent internal-only-transactions case, diagnostics block
- [x] Benchmark updated (6 calculators), a genuine noise finding caught and documented rather than silently smoothed over
- [x] `ruff check` / `mypy` clean throughout
- [x] `docs/adr/0011-...md` written
- [x] No changes to `config_flow.py`, provider interfaces, repository interfaces, or the `Calculator` interface signature

## What was deliberately not included

Per the milestone's own scope: no Time-Weighted Return (correctly identified as blocked on the snapshot mechanism, MILESTONE_4_SPEC.md Section 11 — attempting to approximate it without snapshots would produce misleading numbers), no broker/CSV imports, no write services, no tax-lot accounting, no snapshot storage, no multi-portfolio aggregation, no goals/targets, no dividend analytics, no risk metrics.

## How to validate

```bash
python -m pytest tests/ tests_integration/ -q   # 180 passed
./.ha_test_venv/bin/python -m pytest tests_ha/ -q   # 30 passed
python -m ruff check . custom_components/ tests_ha/ scripts/
python -m mypy
python scripts/benchmark.py --sizes 100,500,1000 --repeats 15
```

## What's next

Per the roadmap in the scoping message: Milestone 6 (snapshot engine + Time-Weighted Return) is the natural next step, since MWR's terminal-value approach is now in place and TWR is the one return metric this milestone correctly declined to approximate without proper snapshot data. `MANUAL_VALIDATION_RUNBOOK.md` also remains the one item flagged since Milestone 2.5 as not yet executed against a real, persistent HA instance.
