# Testing Philosophy

Five independent categories, each with a distinct purpose, distinct location, and deliberately no shared fixtures or dependencies forcing coupling between them. A change to one category's tooling or approach should never require touching another's.

| Category | Location | Purpose | Dependencies | Run via |
|---|---|---|---|---|
| **Unit (Portfolio Engine)** | `tests/` | Verify the engine's calculation logic in isolation — models, calculators, repository/provider I/O boundaries. | `pytest`, `pytest-asyncio`, `pyyaml` only. No `homeassistant`. | `python -m pytest tests/ -v` |
| **Integration (Home Assistant, pure-logic)** | `tests_integration/` | Verify the fetch/compute/mapping logic that sits behind the HA classes (`update_logic.py`, `sensor_mapping.py`) — see ADR-0009. | Same as above — deliberately still no `homeassistant`. | `python -m pytest tests_integration/ -v` |
| **Integration (Home Assistant, real harness)** | `tests_ha/` | Verify the actual HA classes (`ConfigFlow`, `OptionsFlow`, `DataUpdateCoordinator`, `SensorEntity`, `diagnostics.py`) against real Home Assistant core code. | `pytest-homeassistant-custom-component` (pulls in full `homeassistant`) — isolated venv, see `requirements-ha-test.txt`. | `./scripts/setup_ha_test_env.sh` then `.ha_test_venv/bin/python -m pytest tests_ha/ -v` |
| **Performance benchmarks** | `scripts/benchmark.py`, results in `BENCHMARKS.md` | Establish and track a computational baseline (100/500/1000 holdings) — regression detection, not optimization. | Same as unit tests. | `python scripts/benchmark.py --sizes 100,500,1000 --repeats 10` |
| **Manual validation** | `MANUAL_VALIDATION_RUNBOOK.md` | Cover what genuinely can't be automated: Recorder statistics accumulation, behavior across a real HA process restart, real (non-mocked) network failure/recovery. | A real, persistent Home Assistant instance. | Human, following the checklist |

A sixth category is referenced but not yet built out as its own automated thing — **compatibility validation** across multiple HA versions (as opposed to the single pinned version `tests_ha/` currently validates against). Today, `docs/COMPATIBILITY_POLICY.md`'s "minimum supported version" is grounded in whatever `pytest-homeassistant-custom-component` resolves as its `homeassistant` dependency at install time (2025.1 as of Milestone 2.5). A proper compatibility-validation category would run `tests_ha/` against a matrix of pinned HA versions (e.g. oldest-supported and latest, as separate CI jobs) rather than whatever one version happens to resolve. Not built yet because there's been exactly one HA version validated so far — worth introducing once there's a second data point to protect against regressing.

## Why kept separate rather than one big `tests/` tree

- **Dependency isolation**: `tests_ha/` alone justifies pulling in the entire `homeassistant` package. Mixing it into the same tree as `tests/`/`tests_integration/` would force every contributor (and every CI run of the fast suite) to pay that cost, even when working purely on engine logic.
- **Failure attribution**: if `tests_ha/` fails, the problem is almost certainly in HA-facing glue (`coordinator.py`, `sensor.py`, `config_flow.py`) or an HA API change. If `tests/` fails, it's the engine. Keeping them in separate directories with separate run commands makes that attribution immediate rather than something you have to figure out from a mixed failure list.
- **Speed of the inner dev loop**: `tests/` + `tests_integration/` (49 tests total as of Milestone 2.5) run in well under a second with no heavy dependencies — that's the loop a contributor should be running on every save. `tests_ha/` (18 tests, ~1 second once the venv exists, but a real HA install to set up first) is the loop you run before considering a change to the integration layer done, not on every keystroke.
- **Different failure tolerance**: manual validation and (future) multi-version compatibility validation are expected to occasionally surface things that are genuinely version-specific or environment-specific (see Milestone 2.5's DNS-resolver finding) — mixing that expectation into the "should always be green" automated suites would erode trust in the automated ones.

## What "done" means per category, going forward

- A new engine feature (calculator, model field) needs **unit tests** before merge — non-negotiable, this is the fast, cheap layer.
- A new HA-facing feature (entity, config option) needs both **pure-logic integration tests** (the mapping/fetch logic) and **real-harness tests** (the actual HA class behavior) before merge — Milestone 2.5 established this as the bar, not just an option.
- Anything touching Recorder behavior, restart semantics, or real network paths gets a **manual validation runbook entry** added — automated coverage of these is out of scope by design (see the category table above), not an oversight to eventually fix.
- A **benchmark** re-run is warranted whenever a change plausibly affects computational complexity (a new calculator, a change to `build_positions`/allocation grouping) — compare against `BENCHMARKS.md`, update it if the baseline moves for a legitimate reason (new work being measured), investigate if it moves for no clear reason (regression).
