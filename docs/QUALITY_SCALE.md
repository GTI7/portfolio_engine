# Home Assistant Integration Quality Scale — Self-Assessment

This is a genuine self-review against Home Assistant's [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/), written by checking this repository's actual code against each criterion — not a claimed certification. The Quality Scale exists primarily for integrations bundled into HA Core, which go through official maintainer review; a custom integration like this one can't be formally scored, and this document doesn't pretend otherwise. It's here so a maintainer or reviewer knows exactly where things stand without re-auditing the whole codebase, and `manifest.json` deliberately does **not** declare a `quality_scale` value, since that field is meaningful for HA-Core-reviewed integrations in a way a self-assessment isn't.

## Bronze tier — checked against actual code

| Criterion | Status | Where |
|---|---|---|
| `config-flow` | ✅ | `config_flow.py` |
| `config-flow-test-coverage` | ✅ | `tests_ha/test_config_flow.py` — user flow, error path, duplicate rejection, multi-entry, reconfigure |
| `dependency-transparency` | ⚠️ Partial | `manifest.json` requires `pyyaml>=6.0` — a floor, not an exact pin. HA Core requires exact pins for bundled integrations; a custom integration commonly uses a floor instead for compatibility across HA versions' own bundled PyYAML. Worth revisiting if this is ever proposed for HA Core inclusion. |
| `docs-installation` | ✅ | `docs/user/INSTALLATION.md` |
| `docs-configuration-parameters` | ✅ | `docs/user/INSTALLATION.md` (config flow fields), `docs/user/GETTING_STARTED.md` (portfolio setup) |
| `docs-actions` | ✅ | `services.yaml`, `docs/user/BROKER_IMPORT.md`, `docs/user/BACKUP_EXPORT.md` |
| `docs-removal-instructions` | ✅ | `docs/user/INSTALLATION.md`'s "Uninstalling" section |
| `docs-high-level-description` | ✅ | `docs/user/README.md` |
| `docs-known-limitations` | ⚠️ Partial | Scattered across `docs/user/FAQ.md` and `docs/user/TROUBLESHOOTING.md` rather than one consolidated section — the information exists, the organization doesn't fully match this specific criterion's shape |
| `entity-unique-id` | ✅ | Every entity sets `_attr_unique_id` in `sensor.py` |
| `has-entity-name` | ✅ | `_attr_has_entity_name = True` on `_PortfolioEntityBase` |
| `entity-event-setup` | N/A | No event-based entities (this integration is purely polling-based) |
| `runtime-data` | ❌ Not done | Coordinator storage uses `hass.data[DOMAIN][entry.entry_id]` (the pattern established at Milestone 2), not the newer `ConfigEntry.runtime_data` typed-storage convention. A real, tracked gap — migrating touches `__init__.py`, `services.py`, `diagnostics.py`, and `sensor.py`'s coordinator-lookup, which is more invasive than this milestone's remaining budget allows to do safely with full test coverage. Left as a known item for a future pass, not silently ignored. |
| `test-before-configure` | ✅ | Config flow checks the investments path exists before creating an entry |
| `test-before-setup` | ✅ | `async_config_entry_first_refresh()` in `__init__.py` surfaces a broken config as a setup failure, not a silently-unavailable integration |
| `unique-config-entry` | ✅ | Fixed at Milestone 10 — `unique_id` is the investments path itself, so genuinely different setups are allowed while an exact duplicate is still rejected (previously any second entry was blocked outright, regardless of path) |
| `appropriate-polling` | ✅ | `DataUpdateCoordinator` with a user-configurable interval, sensible default (15 min) |
| `common-modules` | ✅ | `const.py`, `coordinator.py` present and used as intended |
| `action-setup` | ✅ | Both services registered in `async_setup_entry` / deregistered on last unload, with `voluptuous` schemas |

## Silver tier — checked against actual code

| Criterion | Status | Where |
|---|---|---|
| `config-entry-unloading` | ✅ | `async_unload_entry` in `__init__.py`, with Repair-issue and service cleanup |
| `entity-unavailable` | N/A | Not a device-connectivity integration; "unavailable" already used correctly for missing/uncomputable metric states |
| `parallel-updates` | ✅ | `PARALLEL_UPDATES = 0` declared in `sensor.py` — coordinator-based entities with no per-entity I/O to throttle, the documented case for this value |
| `reauthentication-flow` | N/A | No authentication — Yahoo Finance's public endpoints need none |
| `test-coverage` | ✅ | 77 real-HA-harness tests, 305 engine unit tests, 40 pure-logic integration tests — see `TESTING.md` |
| `icon-translations` | ❌ Not done | Icons are set via `_attr_icon` in Python (works correctly), not via the newer `icons.json` translation-file convention HA has been moving toward. Functionally equivalent today; a future pass could migrate for consistency with newer integrations. |
| `exception-translations` | ❌ Not done | Service errors (`ServiceValidationError`) use plain English messages, not HA's translation-key exception mechanism. Correct and clear for English-only use; not internationalized. |

## Gold/Platinum tier

Not assessed in detail — those tiers assume Bronze/Silver are both fully met first, which this integration isn't (see the ❌/⚠️ items above). Revisit once those are closed out.

## What's explicitly out of reach in this environment

- **`brands` registration** (an icon/logo submission to the separate `home-assistant/brands` repository) requires a real, public GitHub presence to submit a PR against — not something achievable without one.
- **Actual HACS listing** (default store or even a working custom-repository add) requires a real, public GitHub repository with tagged releases — the files this milestone added (`hacs.json`, `LICENSE`) are the *prerequisites* HACS checks for, not a substitute for actually having the repository. See `docs/RELEASE_CHECKLIST.md` for the concrete steps that still require a real repository to complete.

## Summary

Bronze tier: all criteria checked are met except `dependency-transparency` (partial) and `runtime-data` (not done, tracked). Silver tier: met except `icon-translations` and `exception-translations` (both not done). This is a solid, honest starting position — not a claim of certification, and not a claim that nothing is left to do.
