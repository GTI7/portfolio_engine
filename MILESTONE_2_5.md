# Milestone 2.5: Validation

**Status:** Complete for what's automatable; the manual runbook is written but not yet executed against a real, persistent Home Assistant instance — see "What's genuinely still open" below.

## What changed from Milestone 2's caveats

Milestone 2 shipped with an explicit, honest gap: the HA-specific classes (`coordinator.py`, `__init__.py`, `config_flow.py`, `sensor.py`, `diagnostics.py`) were syntax-checked but never executed against real Home Assistant code. This milestone closes that gap for everything an automated test can cover.

**`pytest-homeassistant-custom-component` is now installed and working in this environment**, in a dedicated virtual environment (kept separate from the project's normal `requirements-test.txt` — see "Why a separate venv" below). **18 new tests in `tests_ha/` run the real `ConfigFlow`, `OptionsFlow`, `DataUpdateCoordinator`, `SensorEntity` subclasses, and `diagnostics.py` against a real (test-mode) `HomeAssistant` core instance** — not mocks of HA's classes, the actual classes.

## What's covered, mapped to the requested checklist

| Item | Covered by | Result |
|---|---|---|
| Config Flow | `tests_ha/test_config_flow.py` (4 tests) | Successful setup, path-not-found error, duplicate-entry abort, minimum-interval enforcement — all against the real `ConfigFlow` |
| Options Flow | `tests_ha/test_options_flow_and_reload.py::test_options_flow_updates_interval_and_reloads` | Confirms the coordinator's actual `update_interval` changes after an options edit, not just that the flow accepts input |
| Integration reload | `test_options_flow_and_reload.py::test_reload_service_call_works` | `hass.config_entries.async_reload()` — entities survive with correct data |
| Entity registration | `tests_ha/test_setup_and_entities.py::test_setup_creates_all_six_entities_with_correct_values` | All six entities exist with correct state and unit after a real setup |
| Device registration | `test_setup_and_entities.py::test_entities_share_one_device_per_portfolio` | Confirms exactly one device, correct name, correct `identifiers` |
| Entity unique IDs | `test_setup_and_entities.py::test_entities_have_stable_unique_ids` | Confirms `unique_id` is entry-derived, not something that could shift |
| Diagnostics download | `tests_ha/test_diagnostics.py` | Full shape assertion against the real `async_get_config_entry_diagnostics` |
| Recovery from provider failures | `tests_ha/test_error_recovery.py::test_provider_failure_marks_entities_unavailable_not_crashed` + `test_recovers_after_transient_failure_clears` | Entities go `unavailable` (not crash, not stale-frozen), and recover automatically on the next successful refresh |
| Recovery from malformed YAML | `test_error_recovery.py::test_malformed_yaml_leaves_entry_not_ready_not_crashed` | Confirmed: `ConfigEntryState.SETUP_RETRY`, not an unhandled exception |
| Recovery from temporary network failures | Same mechanism as "provider failures" above — a `ConnectionError` from the provider is the general case a real DNS/timeout failure would also produce | Covered at the coordinator level; real network-path behavior is in the manual runbook (see below) |
| Recorder statistics | **Not automatable here** | See "What's genuinely still open" |
| Reload after Home Assistant restart | **Partially** — `async_reload` is tested; a full process restart is not | See "What's genuinely still open" |

Two items (no portfolios configured at all, and invalid holding data specifically, distinct from generically-malformed YAML) were added beyond the original list because writing the malformed-YAML test surfaced them as adjacent, easy-to-get-wrong cases worth covering explicitly — both confirmed to fail gracefully (`SETUP_RETRY`, not a crash).

## What's genuinely still open

Recorder statistics and true restart-persistence need a long-running, real HA instance (accumulating statistics over multiple real update cycles; observing behavior across an actual process restart, not just `async_reload` within the same test process) — an ephemeral test-harness `hass` instance can't faithfully represent either. **`MANUAL_VALIDATION_RUNBOOK.md`** is written to cover exactly these, plus the real-network version of the failure-recovery tests, as a checklist to run against a real deployment. This wasn't executed as part of this delivery because doing so requires deploying to and restarting an actual persistent Home Assistant installation, which this environment doesn't have (consistent with the same tooling boundary noted in Milestone 2 — no filesystem access to a live HA config directory here).

## Two real bugs-that-weren't, found by writing these tests

Worth surfacing because this is exactly what "validate before building more" is for:

1. **A genuine environment-specific finding, not a code bug**: the very first full-setup test, run without mocking the price provider, hit a real `aiodns`/`pycares` incompatibility in this sandbox (`Channel.getaddrinfo() takes 3 positional arguments...`) when the coordinator tried to actually resolve `query1.finance.yahoo.com`. The coordinator's error handling worked correctly — it caught the failure and left the entry in `SETUP_RETRY` rather than crashing — but real network behavior in this specific sandbox couldn't be trusted, which is exactly why `mock_price_provider` exists and why the manual runbook calls for testing real network failure against an actual instance instead.
2. **A test-hygiene finding**: merely constructing a real `aiohttp.ClientSession` (via `async_get_clientsession`), even when never used because the provider call itself was mocked, left a background cleanup thread running past test teardown, which the HA harness's resource-leak detector correctly flagged. Fixed by also mocking `async_get_clientsession` in tests — not a bug in `coordinator.py` itself, but a reminder that "mock the network call" and "avoid creating real network resources at all" are different things worth doing together in tests.

## Why a separate venv (`requirements-ha-test.txt`, `scripts/setup_ha_test_env.sh`)

`pytest-homeassistant-custom-component` pulls in the full `homeassistant` core package — a large, fast-moving dependency the rest of this project (the engine, the pure-logic `tests_integration/` suite) has no use for. Keeping it in its own venv, installed via its own requirements file and setup script, means `pip install -r requirements.txt -r requirements-test.txt` (the normal contributor path for `tests/` and `tests_integration/`) stays fast and light, while `tests_ha/` is available as an explicit, separate, opt-in step — and the natural CI shape: two jobs, one fast (engine + integration pure-logic tests, every commit), one heavier (the HA harness, still every commit, just a separate job so its dependency install doesn't slow down the fast feedback loop).

```bash
./scripts/setup_ha_test_env.sh
.ha_test_venv/bin/python -m pytest tests_ha/ -v   # 18 passed
```

**How discovery works** (worth documenting since it's non-obvious): `pytest-homeassistant-custom-component`'s default `hass` fixture always points `hass.config.config_dir` at a fixed directory bundled inside the installed package itself (`.../pytest_homeassistant_custom_component/testing_config/`). HA's loader mounts `<config_dir>/custom_components` once at `hass` construction time — changing `hass.config.config_dir` afterward doesn't retroactively remount it. The standard, and only clean, fix is a symlink: `testing_config/custom_components/portfolio_engine` → this repo's real `custom_components/portfolio_engine`, created once by `setup_ha_test_env.sh`. This is standard practice for testing HA custom integrations with this harness, not a workaround specific to this project.

## Compatibility and entity-API policy

Two new policy documents, both introduced now (not before) because they needed real validated data to be more than aspirational:

- **`docs/COMPATIBILITY_POLICY.md`** — minimum supported HA version (2025.1, the version actually validated by `tests_ha/`, not a guess), a compatibility policy tied to that test suite as the source of truth going forward, a deprecation policy, and a release-notes-for-breaking-changes requirement.
- **`docs/ENTITY_API_POLICY.md`** — operationalizes ADR-0006 into a concrete table (what each of the six entities means, frozen) and six specific rules, including two that ADR-0006 implied but didn't spell out: unit/device-class changes are breaking (they affect Recorder statistics continuity), and the `positions` attribute's per-item shape is allowed to grow additively without being treated as a breaking change to the entity itself.

## How to run everything

```bash
# Fast path — engine + integration pure-logic tests (unchanged from Milestone 2)
python -m pytest tests/ tests_integration/ -q   # 40 passed

# HA harness — separate venv, see above
./scripts/setup_ha_test_env.sh
.ha_test_venv/bin/python -m pytest tests_ha/ -v   # 18 passed

# Style
python -m ruff check . custom_components/ tests_ha/
```

## Validation checklist

- [x] `pytest-homeassistant-custom-component` installed and working (isolated venv)
- [x] Real `ConfigFlow`, `OptionsFlow`, `DataUpdateCoordinator`, `SensorEntity`, `diagnostics.py` all exercised by 18 passing tests against real HA core code
- [x] Config flow, options flow, reload, entity registration, device registration, unique IDs, diagnostics download, provider-failure recovery, and malformed-YAML recovery all automated and passing
- [x] `ruff check` clean on `tests_ha/` too
- [x] `MANUAL_VALIDATION_RUNBOOK.md` written for the items that need a real persistent instance (Recorder statistics, true restart persistence, real-network failure/recovery)
- [ ] Manual runbook actually executed against a live HA instance — explicitly not done here, flagged rather than assumed
- [x] `docs/COMPATIBILITY_POLICY.md` and `docs/ENTITY_API_POLICY.md` written, grounded in what was actually validated rather than aspirational numbers

## Next

Per the milestone guidance: Milestone 3, currency-only scope (Currency Provider abstraction, exchange-rate service, multi-currency calculations, base-currency conversion, validation and testing) — no other functionality. The one prerequisite worth naming before starting it: whoever runs the manual validation runbook against a real instance should do so before or alongside Milestone 3, so currency support gets validated against a codebase already confirmed to behave correctly in real Home Assistant, not one still carrying an open validation question.
