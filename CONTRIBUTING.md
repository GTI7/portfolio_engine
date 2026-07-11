# Contributing

## Before you start

Read [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the current priority and known technical debt, and [`docs/adr/`](docs/adr/) for why the architecture looks the way it does. This project has a documented history (`MILESTONE_1.md` through `MILESTONE_10.md`) — a change that contradicts a prior decision should either follow the existing ADR process (see `docs/adr/template.md`) or explain why the decision no longer holds, rather than silently drifting from it.

## Development setup

```bash
pip install -r requirements.txt -r requirements-test.txt
pip install mypy ruff   # matches pyproject.toml's [tool.mypy] / [tool.ruff] config
pre-commit install
```

(`pyproject.toml`'s `[project]` table isn't set up as an installable package — there's no single top-level package to discover, by design, since `engine/`, `providers/`, `repositories/`, and `custom_components/portfolio_engine/` are deliberately separate. Install from the requirements files directly rather than `pip install -e .`.) `.pre-commit-config.yaml` runs `ruff` (lint + format) and `mypy` (scoped to `engine/`, `repositories/`, `providers/` — see `pyproject.toml`'s own comment on why `tests/` is excluded from strict typing) on every commit.

## Running the tests

See [`TESTING.md`](TESTING.md) for the full breakdown of test categories. The short version:

```bash
pytest                              # tests/ + tests_integration/, fast, no HA install needed
./scripts/setup_ha_test_env.sh      # one-time
.ha_test_venv/bin/python -m pytest tests_ha/ -v   # real Home Assistant harness
```

CI (`.github/workflows/tests.yml`) runs both on every push and pull request against `main` — a green run is expected before merge, not optional.

## What a PR needs

Per `TESTING.md`'s "What 'done' means" section:

- A new engine feature (calculator, model field) needs **unit tests** in `tests/`.
- A new HA-facing feature (entity, config option) needs both **pure-logic integration tests** (`tests_integration/`) and **real-harness tests** (`tests_ha/`).
- A new public entity needs a contract entry in `docs/ENTITY_CONTRACTS.md` (see `docs/ENTITY_API_POLICY.md` for the stability rules behind it).
- A behavior change worth a release note gets a `CHANGELOG.md` entry under `[Unreleased]`, tagged `[engine]`, `[integration]`, or `[process]` per the convention at the top of that file.
- Bump `scripts/benchmark.py`'s baseline in `BENCHMARKS.md` if the change plausibly affects computational complexity.

## Code style

`ruff` (lint + format) and `mypy --strict` (for `engine/`, `repositories/`, `providers/` only) are enforced via pre-commit — run `pre-commit run --all-files` before opening a PR if you didn't install the hook.

## Reporting bugs / requesting features

Use the issue templates under **Issues → New issue**. For security vulnerabilities, see [`SECURITY.md`](SECURITY.md) instead of opening a public issue.
