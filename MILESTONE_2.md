# Milestone 2: HA Wiring

**Status:** Complete for the agreed scope; two validation caveats flagged explicitly below (read before treating this as production-ready).

## What's included

`custom_components/portfolio_engine/` — a real Home Assistant custom integration:

- **`manifest.json`, `const.py`** — standard integration metadata; scope constants (single portfolio, single provider) kept in one place.
- **`config_flow.py`** — `ConfigFlow` (investments path + initial update interval, with existence validation on the path and a duplicate-entry guard) and `OptionsFlow` (update interval, editable post-setup without recreating the entry).
- **`coordinator.py`** — `PortfolioCoordinator(DataUpdateCoordinator)`. Thin per ADR-0009: constructs the concrete `YamlRepository` + `YahooFinanceProvider` + `PortfolioEngine`, and delegates the actual fetch/compute work to `update_logic.py`. Converts any failure (missing portfolios, network error, bad YAML) into `UpdateFailed` so HA's standard retry/backoff and entity-`unavailable` handling apply.
- **`__init__.py`** — `async_setup_entry` / `async_unload_entry` / reload-on-options-change lifecycle. First refresh happens during setup so a broken config fails setup visibly rather than installing successfully and failing silently later.
- **`sensor.py`** — exactly the six entities agreed in `MILESTONE_2_PLAN.md` (now treated as shipped, per ADR-0006): `portfolio_value`, `portfolio_total_invested`, `portfolio_total_profit`, `portfolio_roi`, `portfolio_cash_balance`, `portfolio_positions` (attribute-only, holds the full positions table). Proper `unique_id`, `DeviceInfo` (one device per portfolio), and `SensorDeviceClass.MONETARY` + `SensorStateClass.TOTAL` on the currency-valued sensors so HA's own long-term statistics work on them for free.
- **`diagnostics.py`** — powers Settings → Devices & Services → ⋮ → Download Diagnostics: redacted entry config, coordinator health (`last_update_success`, `last_error`, update interval), and a summary snapshot.
- **`update_logic.py`, `sensor_mapping.py`** — the actual logic (fetch, compute, map to entity values), deliberately kept free of `homeassistant.*` imports per ADR-0009, so it's testable in this environment without a full HA install.
- **`engine/`, `repositories/`, `providers/`** — vendored copies of the Milestone 1 packages (import paths adjusted to be relative within the integration). See "A packaging note" below for why this is copied rather than referenced.

## What was explicitly kept out (per this milestone's guidance: "expose the engine, don't expand it")

- No allocation, performance, or diagnostic-sensor entities beyond the six agreed — the engine already computes allocation/performance data (visible in `coordinator.data` and diagnostics), it's just not exposed as separate entities yet.
- No provider or repository *choice* in the config flow — Yahoo Finance + YAML are hardcoded for Milestone 2. Multi-provider selection is a config-flow enhancement for a later milestone, once there's a second provider to choose from.
- No multi-portfolio — `update_logic.py` takes `portfolios[0]`, documented inline as the Milestone 2 boundary.
- No Repairs platform, no currency conversion, no event-driven recalculation (per ADR-0005, unchanged) — full recompute per coordinator tick.

## Two validation caveats — read before deploying

This environment has no Home Assistant installation and no filesystem access to a live HA config directory (the connected HA instance in this conversation is reachable only through its own API/automation tools, not raw file deployment). Two consequences:

1. **`coordinator.py`, `__init__.py`, `config_flow.py`, `sensor.py`, `diagnostics.py` are syntax-checked (`python -m py_compile`, all pass) and written to current HA conventions from documented knowledge, but are not executed against a real `HomeAssistant` instance or the `pytest-homeassistant-custom-component` test harness.** The logic they call (`update_logic.py`, `sensor_mapping.py`) *is* fully tested — 9 passing tests exercising the actual fetch/compute/mapping behavior. What's untested is the HA-specific glue: whether `DataUpdateCoordinator`'s constructor arguments are exactly right for the HA version you're running, whether `entry.async_on_unload` behaves as expected, whether `DeviceInfo`/`unique_id` register cleanly. This is the honest boundary of what could be verified here.
2. To close that gap, install this in a real (or test) Home Assistant instance and confirm: the config flow completes without error, all six entities appear with sensible values, Download Diagnostics produces a sane JSON dump, and reloading after an options change (update interval) doesn't error.

For local automated coverage of the HA-specific classes themselves (recommended before considering this production-ready):

```bash
pip install pytest-homeassistant-custom-component
# then write coordinator/config_flow tests using its fixtures
# (hass, MockConfigEntry, etc.) per its own documentation
```

This wasn't done as part of this delivery because it pulls in the full Home Assistant core package — a heavy dependency to add for what is, by design (ADR-0009), thin glue code with little logic of its own. That tradeoff is a judgment call, documented rather than hidden.

## A packaging note: vendored vs. referenced engine code

`engine/`, `repositories/`, `providers/` are physically copied into `custom_components/portfolio_engine/` rather than imported from the standalone `portfolio_engine/` package at the repo root. Custom Home Assistant integrations must be self-contained (HA doesn't install arbitrary sibling Python packages from a repo layout) — vendoring is the pragmatic choice for a single-repo delivery. If the engine is ever published as its own installable package (setuptools/PyPI, consistent with ADR-0007's independent versioning), `manifest.json`'s `requirements` would declare it as a version-pinned dependency instead, and this copy would be removed. Not done now because there's no package registry target yet — noted as a natural Milestone 3+ cleanup, not a blocking issue today.

## How to validate what could be validated here

```bash
# Engine (Milestone 1, unaffected in behavior, extended for cash — 31 tests)
python -m pytest tests/ -v

# Integration pure-logic layer (Milestone 2's testable core — 9 tests)
python -m pytest tests_integration/ -v

# Everything together
python -m pytest tests/ tests_integration/ -q   # 40 passed

# Style/type checking (engine + repositories + providers; see mypy note below)
python -m ruff check .
python -m mypy   # scoped to engine/repositories/providers per pyproject.toml

# Lint the integration code too (doesn't need homeassistant installed)
python -m ruff check custom_components/

# Syntax-check the HA-dependent files (can't fully type/run-check without HA installed)
python -m py_compile custom_components/portfolio_engine/{__init__,coordinator,config_flow,sensor,diagnostics}.py
```

**mypy note:** running mypy against `custom_components/portfolio_engine/update_logic.py` and `sensor_mapping.py` in isolation is clean (they're pure Python). Running it against the package as a whole pulls in `coordinator.py`/`__init__.py` transitively (mypy resolves the containing package to follow relative imports) and reports errors there — expected, since `homeassistant` isn't installed and its types resolve to `Any` without stubs. Install `homeassistant` or `homeassistant-stubs` locally for a real type-check of the integration files.

## Migration notes

- `holdings.yaml` gains a new optional field, `cash_balance` (defaults to `0.0` if omitted) — additive, no migration needed for existing files.
- The `Calculator.calculate()` internal interface changed shape (`(portfolio, positions)` instead of `(positions, base_currency)`, ADR-0008) — this only matters if you wrote a custom calculator against Milestone 1's interface; none exist outside this repo yet, so no external migration is needed.
- To try the integration: copy `sample_investments/` to `<ha_config>/investments/` (or point the config flow at wherever you place it), then add the integration via Settings → Devices & Services → Add Integration → Portfolio Engine.

## Updated validation checklist

- [x] `pytest tests/ tests_integration/` passes (40/40)
- [x] `ruff check .` and `ruff check custom_components/` both clean
- [x] `mypy` clean on engine/repositories/providers (both the standalone package and, in isolation, the vendored copy's pure-logic modules)
- [x] All HA-dependent files pass `py_compile` (syntax-valid)
- [x] Entity surface matches `MILESTONE_2_PLAN.md` exactly — no scope creep
- [x] Cash balance is a first-class model field, not a Milestone-2-only special case (ADR-0008)
- [x] ADR-0008 (cash) and ADR-0009 (thin coordinator / testable update logic) written
- [ ] **Not done, flagged above:** verified against a real Home Assistant instance or `pytest-homeassistant-custom-component`

## Next milestone

Per the "expose, don't expand" principle just applied to Milestone 2, the natural next increment is validating this milestone for real (deploy to an actual HA instance, confirm the config flow and entities work end-to-end) before adding Milestone 3's currency service — architecture is frozen; the priority from here is implementation, validation, and closing exactly the gap flagged above.
