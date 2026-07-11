## What changed and why

<!-- Not just "what" - the reason, per this project's own documentation style (see any MILESTONE_*.md for the tone to match). -->

## Test coverage

- [ ] New/changed engine logic has **unit tests** in `tests/`
- [ ] New/changed HA-facing behavior has **pure-logic integration tests** in `tests_integration/` and/or **real-harness tests** in `tests_ha/`
- [ ] `pytest` (fast suite) passes locally
- [ ] `tests_ha/` passes (either locally via `.ha_test_venv`, or via CI on this PR)

## Documentation

- [ ] `CHANGELOG.md` entry added under `[Unreleased]`, tagged `[engine]` / `[integration]` / `[process]`
- [ ] New public entity: `docs/ENTITY_CONTRACTS.md` entry added, `docs/ENTITY_API_POLICY.md` rules followed
- [ ] Architectural decision worth recording: new ADR added under `docs/adr/` (see `docs/adr/template.md`)
- [ ] `BENCHMARKS.md` re-run if this plausibly affects computational complexity

## Checklist

- [ ] `pre-commit run --all-files` passes (ruff + mypy)
- [ ] No engine version bump unless `engine/` calculation logic actually changed (see `docs/adr/0007-independent-engine-versioning.md`)
