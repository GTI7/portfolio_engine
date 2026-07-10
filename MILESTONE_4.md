# Milestone 4: Transaction History

**Status:** Complete for the scope in `MILESTONE_4_SPEC.md`. Implemented in the six phases agreed before coding began, each phase's tests passing before the next started.

## Phases, as executed

| Phase | What shipped | Tests added | Cumulative |
|---|---|---|---|
| 1. Domain model | `TransactionType`, `Transaction` (full validation), `Portfolio.transactions` | 43 | 82 |
| 2. Repository | `PortfolioRepository.supports_transactions`/`.async_get_transactions()`, `YamlRepository` reading `transactions.yaml`, duplicate-ID detection | 12 | 94 |
| 3. Transaction replay | `engine/transaction_replay.py` — `replay_transactions()` → `TransactionReplayResult` | 26 | 120 |
| 4. Calculators | `ReconciliationCalculator`, `TransactionCalculator`, result dataclasses, tolerance handling | 16 | 136 |
| 5. HA integration | Coordinator registration, `sensor_mapping.py`, two entities, diagnostics | 42 (17 pure-logic + 25 real-harness) | 178 |
| 6. Documentation | ADR-0010 → Accepted, `CHANGELOG.md`, `docs/ENTITY_CONTRACTS.md`, `BENCHMARKS.md` | — | 178 |

Engine bumped to **v0.4.0** (additive interface: `Transaction`/`TransactionType`/`Portfolio.transactions` are new, `PortfolioRepository` gained concrete non-abstract methods, `Calculator.calculate(portfolio, positions)` itself is unchanged). Integration `manifest.json` version unchanged — no HA-facing breaking behavior, just two new entities, which is an additive change under `ENTITY_API_POLICY.md`.

## Two design changes made before Phase 1, from review

Both accepted and reflected in `MILESTONE_4_SPEC.md` before any code was written:

1. **`Transaction.amount` is an unsigned magnitude**, not a signed cash-flow value. The original draft encoded direction twice (in `type` and in `amount`'s sign), which allowed `{type: BUY, amount: +1000}` — schema-valid, semantically nonsensical. `TransactionType` alone now determines direction via `CASH_EFFECT_SIGN`, applied in exactly one place (`transaction_replay.py`).
2. **`transaction_replay.py` returns one bundled `TransactionReplayResult`** (`holdings` + `cash_balance`, now also `warnings`) instead of two separate functions — so future fields are additive rather than new parallel return values every caller has to learn about.

## Two things found during implementation, not anticipated in the spec

Both are the kind of "genuine, demonstrated need" the project's governing principle asks for — found by building and testing, not imagined in advance:

1. **Oversold/incomplete-log positions.** `Holding.__post_init__` forbids negative shares (correct for user-declared config) — but `transaction_replay.py` needs to represent a transaction log implying negative shares (a SELL recorded before its BUY, or a log that doesn't start from account inception) without crashing, since rejecting it would defeat reconciliation's entire purpose. Fixed with an internal, unvalidated `_Accumulator` during replay; only the final, clamped-to-zero result becomes a real `Holding`, with a `TransactionReplayResult.warnings` entry recording what was clamped. Covered by `test_sell_without_prior_buy_is_clamped_to_zero_with_warning` and `test_overselling_more_than_held_is_clamped_with_warning`.
2. **An O(n²) performance regression**, caught by `scripts/benchmark.py`, not a code review. `ReconciliationCalculator` originally looked up each symbol's declared `Holding` via a linear scan over `positions` inside a loop over every symbol. Fixed with a `{symbol: Holding}` dict built once. 1000-holding benchmark time: ~19.7ms → ~6.3ms. Full account in `BENCHMARKS.md`.

## Two things caught only by the real HA harness

Neither was visible in the pure-logic (`tests_integration/`) tests — both are exactly the class of bug that category of test can't see, and exactly what `tests_ha/` exists for:

1. **Missing translations.** The two new entities initially resolved to friendly name "None" (`sensor.demo_portfolio_none`) because `strings.json`/`translations/en.json` had no entry for their `translation_key`s. Fixed by adding `portfolio_transaction_count`/`portfolio_reconciliation` entries.
2. **A wrong test fixture**, not a code bug — an early version of the "matching transactions" HA test declared `cash_balance=1000.0` while the transaction log it supplied reconciled to `0.0`, so the test that should have proven "ok" reconciliation was actually proving "discrepancy." Caught immediately because the harness runs the real `ReconciliationCalculator`, not a mock of it.

## Validation checklist (from MILESTONE_4_SPEC.md Section 17)

- [x] `Transaction`/`TransactionType` implemented per the (revised) spec, full validation coverage (43 tests)
- [x] `Portfolio.transactions` field added; all pre-Milestone-4 tests pass unmodified
- [x] `PortfolioRepository.supports_transactions`/`async_get_transactions` concrete/default methods; `YamlRepository` fully implements both
- [x] `engine/transaction_replay.py` implemented and heavily unit-tested (26 tests — the largest single test file in the project, matching the "spend most of the testing effort here" guidance)
- [x] `ReconciliationCalculator` and `TransactionCalculator` implemented, registered, unit-tested (16 tests)
- [x] Two new entities implemented with `docs/ENTITY_CONTRACTS.md` entries, covered by real-HA-harness tests including `"no_data"` and `"discrepancy"` cases specifically
- [x] `diagnostics.py` includes the reconciliation block
- [x] All three test categories pass; 178 tests total, up from 71 at Milestone 3
- [x] `ruff check` / `mypy` clean throughout
- [x] `docs/adr/0010-...md` written and moved to Accepted
- [x] Existing single- and multi-currency portfolios without `transactions.yaml` behave exactly as before — reconciliation reports `"no_data"`, nothing else changes
- [x] No changes to `config_flow.py`, provider interfaces, or the `Calculator` interface signature

## How to validate

```bash
python -m pytest tests/ tests_integration/ -q   # 153 passed
./.ha_test_venv/bin/python -m pytest tests_ha/ -q   # 25 passed  (./scripts/setup_ha_test_env.sh first if needed)
python -m ruff check . custom_components/ tests_ha/ scripts/
python -m mypy
python scripts/benchmark.py --sizes 100,500,1000 --repeats 15
```

## What's next

Per the milestone guidance: architecture is frozen, priority is implementation/validation/feature delivery. Currency support (Milestone 3) and transaction history (this milestone) are both in place; natural next candidates are dividend income aggregation (transactions already capture dividends, a dedicated calculator/entity is separate future work) or executing `MANUAL_VALIDATION_RUNBOOK.md` against a real, persistent HA instance — still the one item flagged since Milestone 2.5 as not yet done in this environment.
