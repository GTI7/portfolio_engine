# ADR 0009: Push Logic Out of HA Classes Into Testable Pure Functions

**Status:** Accepted
**Date:** 2026-07-09

## Decision

`coordinator.py`'s `PortfolioCoordinator(DataUpdateCoordinator)` and `sensor.py`'s `SensorEntity` subclasses contain no logic beyond calling into `update_logic.async_fetch_portfolio_data()` and `sensor_mapping.py`'s functions, respectively. Those two modules are plain Python — no `homeassistant.*` imports — and carry the actual "fetch, compute, map to entity values" logic, fully testable with pytest and fake repository/provider/data fixtures.

## Reason

This milestone's guidance is explicit: "the Home Assistant integration should remain as thin as possible... its primary responsibility is to connect Home Assistant to the Portfolio Engine, not to duplicate business logic." There's a second, practical reason specific to this project's development environment: this codebase is developed and tested without a full Home Assistant installation available (no `pytest-homeassistant-custom-component` harness in the dev environment used to build Milestone 2). Classes that subclass `DataUpdateCoordinator`/`SensorEntity`/`ConfigFlow` can't be imported, let alone tested, without `homeassistant` installed. Concentrating the actual logic in HA-independent functions means that logic is verified now, in this environment, with the same pytest suite as the engine — rather than shipping untested and only discovering bugs once installed in a real Home Assistant instance.

## Alternatives Considered

- **Put fetch/compute/mapping logic directly in `PortfolioCoordinator._async_update_data()` and each `SensorEntity.native_value`** — the more common pattern in smaller HA integrations, and not wrong in general. Rejected here specifically because it would leave 100% of Milestone 2's actual logic untested in this development environment, which is a concrete, present limitation (not a hypothetical one) that justifies the extra indirection.
- **Install `pytest-homeassistant-custom-component` and test the real HA classes directly** — the more thorough approach, and the one recommended for the user's own local development going forward (see MILESTONE_2 notes on how to run it). Not done in this delivery because it pulls in the full Home Assistant core package, which is a heavy, slow addition to validate for what amounts to thin glue code — better spent as the reader's own local verification step, with the logic that actually matters already covered here.

## Consequences

- `coordinator.py` and `sensor.py` are short and low-risk (they have little logic to get wrong), at the cost of one extra file each (`update_logic.py`, `sensor_mapping.py`) and one extra layer of indirection to follow when reading the code.
- Anyone adding a new sensor in a later milestone should add a corresponding pure function to `sensor_mapping.py` first, then a thin `SensorEntity` wrapping it — not logic directly in the entity class — to keep this property intact.
- This doesn't replace real HA-harness testing entirely: `coordinator.py`'s handling of `UpdateFailed`, entry reload on options change, and `sensor.py`'s `DeviceInfo`/`unique_id` wiring are HA-specific glue that this pattern deliberately keeps thin *and untested by this delivery* — validating those still requires the real harness or a live HA instance, and is called out explicitly as a follow-up validation step rather than silently assumed to be correct.
