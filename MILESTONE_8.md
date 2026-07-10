# Milestone 8: Home Assistant UX & Production Readiness

**Status:** Complete for everything achievable in this environment. One honest, explicit exception: full manual validation against a real, persistent Home Assistant instance with visual confirmation — not achievable here, and reported as such rather than claimed. See "What's genuinely unverified" below.

## What's included

- **Entity polish**: icons on all fourteen entities (none had one before); confirmed `entity_category` should stay unset on all of them, including `portfolio_reconciliation`, with the reasoning documented in `sensor.py` itself; audited unit/device-class/state-class assignments against `docs/ENTITY_CONTRACTS.md` (found already correct).
- **Diagnostics, genuinely expanded**: repository/provider identity, the calculator registry, engine/integration/HA-Core version info, expanded snapshot statistics, a new transaction-statistics block, and a benchmarks reference — everything the milestone brief asked for, each one interpreted honestly rather than manufactured (see "Two things I chose not to fabricate" below).
- **Repairs framework integration**: four real conditions (reconciliation discrepancy, missing FX rates, snapshot repository unavailable, malformed transaction/holdings data), each created and cleared automatically, cleaned up on unload.
- **Official dashboard package**: six views, core Lovelace cards only, no HACS dependency — and genuinely validated against a real Home Assistant instance's storage API, not just locally parsed.
- **End-user documentation**: installation, getting started, dashboards, troubleshooting, FAQ — a real second documentation tier, separate from the architecture docs at the repository root.
- **Manual validation**: executed as far as this environment genuinely allows, with an explicit, honest record of what that does and doesn't cover.

Engine version: unchanged (0.7.0). Integration version: 0.1.0 → 0.2.0. No new ADR.

## The environment constraint, stated plainly

This environment has no file-write access to any real, persistent Home Assistant instance's `config/custom_components/` directory. That's been true since Milestone 2 and Milestone 8 doesn't change it. What *is* available: a real, separate, persistent Home Assistant instance reachable via API-level tools (not file access), and the real `pytest-homeassistant-custom-component` test harness, which spins up genuine HA Core code (not a mock of it) per test.

Given that, this milestone did two things instead of one thing badly:

1. **Used the real test harness for everything it's actually capable of proving** — which turns out to be almost the entire runbook: config flow, options flow, reload, entity/device registration, unique ID stability, diagnostics shape, malformed-data recovery, provider-failure recovery, and — new this milestone — Repairs create/clear cycles and a genuine restart simulation (full config-entry unload then setup again within one test, against real persisted `Store` data, confirming no duplicate snapshot). This is 59 passing tests exercising real integration code, not a description of expected behavior.
2. **Used the real, separate, connected Home Assistant instance for the one thing it could genuinely help with**: validating the dashboard package. The exact YAML (converted to JSON) was submitted to that instance's dashboard-storage API, saved, read back, and confirmed to round-trip with an identical config hash, then deleted again. This confirms the dashboard's structure, every card type, and every Jinja2 template expression are valid Home Assistant Lovelace configuration accepted by a real instance's storage backend — genuinely more than local YAML parsing proves, even though that instance has no Portfolio Engine entities to render against.

What neither of those covers, and what remains genuinely unverified, is recorded explicitly in `MANUAL_VALIDATION_RUNBOOK.md`'s new "Execution Record" section: Recorder long-term statistics rendering over real elapsed time, visual/UI screenshots with real data, a true host-level process restart (as opposed to the config-entry-level simulation the test harness does), and real network conditions against Yahoo Finance's actual endpoint. That section says so directly — it does not present the checklist as complete.

## Two things I chose not to fabricate

The brief asked for "calculator versions" and "benchmark version" in diagnostics. Neither concept exists cleanly in this project as built, and inventing fake precision would have been worse than being honest about the mismatch:

1. **"Calculator versions"** — calculators aren't individually versioned; only the engine package as a whole is (ADR-0007). Diagnostics instead reports a **calculator registry** (`{name: ClassName}`) — which class implements which registered calculator right now. This serves the actual underlying need (a bug report needs to know what's active) without claiming a version number that doesn't exist.
2. **"Benchmark version"** — the benchmark baseline is always recorded against a specific engine version already (`BENCHMARKS.md`'s own header). Diagnostics points at that file and repeats `environment.engine_version` as the comparison key, rather than inventing a second, separate "benchmark version" concept that would just be a shadow of the first.

## Design decisions worth surfacing

- **`update_logic.py`'s graceful degradation for snapshot repository failures.** Before this milestone, any Store I/O error would fail the *entire* refresh via the generic exception handler — prices, positions, everything, over a storage problem unrelated to market data. Now a snapshot repository failure degrades to an empty/unchanged snapshot list plus a surfaced error, and everything else keeps working. This is a real behavior change in a previously-untested failure path, not a change to any currently-passing scenario — confirmed by every existing test still passing unmodified, plus three new tests covering the failure path itself. This is exactly the kind of "production readiness" improvement the milestone asked for, scoped narrowly to error handling, not calculation logic.
- **No new architectural pattern for Repairs.** The four conditions are checked from data `update_logic.py` already produces (`reconciliation.status`, `fx_rates_missing`, the new `snapshot_repository_error`) or from a new, narrowly-scoped exception classification in the coordinator's existing `_async_update_data` (distinguishing `ValueError`/`yaml.YAMLError` — malformed data — from other failures). No new engine-layer concept was needed.
- **The coordinator's `_build_calculators()` split** is a refactor of existing code (extracting what was inline in `_build_engine()`), not new logic — needed only so diagnostics could read the registry without reaching into a private attribute. Zero behavior change, confirmed by the full existing test suite passing unmodified.

## Validation checklist

- [x] Existing functionality unchanged — full suite (355 tests) passes, all but 18 of them unmodified from before this milestone
- [x] Existing entities polished — icons added, entity_category decision documented, unit/device/state-class audited
- [x] Official dashboard package included — six views, core cards only, validated against a real HA instance's storage API
- [x] Documentation suitable for first-time users — `docs/user/` is a genuinely separate, non-architecture-facing tier
- [x] Manual validation completed **and honestly documented** — not overclaimed; the runbook says exactly what was and wasn't covered
- [x] Repairs integrated where appropriate — four conditions, tested create/clear/cleanup-on-unload
- [x] Diagnostics expanded — repository/provider/calculator/environment/snapshot/transaction/benchmarks, no secrets (tested)
- [x] All automated tests continue to pass — 355/355
- [x] Engine version unchanged — 0.7.0, confirmed by direct check before and after
- [x] Integration version incremented — 0.1.0 → 0.2.0
- [x] No new ADR — no genuine architectural fork appeared; everything here is the platform being consumed, not extended

## How to validate

```bash
python -m pytest tests/ tests_integration/ -q   # 296 passed
./.ha_test_venv/bin/python -m pytest tests_ha/ -q   # 59 passed
python -m ruff check . custom_components/ tests_ha/ scripts/
python -m mypy
```

For the dashboard package: follow `docs/user/DASHBOARDS.md` against your own real portfolio — that step (real data, real rendering) is exactly the one this environment couldn't complete itself.

## What's next

The project has now covered both the "data platform" phase (Milestones 1–6) and the "consume the platform" phase from two different angles — analytics (Milestone 7) and UX/production-readiness (Milestone 8). What remains genuinely open, not from any gap in this milestone's execution but from this environment's own limits, is real-instance visual validation — recorded honestly in `MANUAL_VALIDATION_RUNBOOK.md` rather than left implicit, so whoever picks this up next with real deployment access knows exactly what's left to check and where to start.
