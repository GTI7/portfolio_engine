# Milestone 1 — Addendum: Tooling, Versioning, Benchmarks

Added after Milestone 1 review, before starting Milestone 2. Nothing in this
addendum changes the engine's behavior — it's process and measurement
infrastructure only.

## 1. Static type checking

`pyproject.toml` configures `mypy --strict` scoped to `engine/`,
`repositories/`, `providers/` (deliberately **not** `tests/` — test fixtures
trade some type precision for readability, an acceptable tradeoff there
specifically). Three pre-existing type gaps were found and fixed:

- `providers/yahoo_finance.py`: `FetchFn`'s `dict` needed a type argument (`dict[str, Any]`).
- `repositories/yaml_repository.py`: `portfolios` needed an explicit `list[Portfolio]` annotation (mypy couldn't infer the element type from an empty list literal).
- `engine/portfolio_engine.py`: `run()`'s return type needed a type argument (`dict[str, Any]`).

```bash
python -m mypy   # Success: no issues found in 14 source files
```

## 2. Development tooling

- **Ruff** for linting *and* formatting (`ruff format` is Black-compatible, so a separate Black install wasn't added — one tool covering both jobs, per the "prefer simplicity" principle). Config in `pyproject.toml` under `[tool.ruff]`.
- **pre-commit** (`.pre-commit-config.yaml`): ruff (lint + format), mypy (scoped to the three source packages), and the standard trailing-whitespace/end-of-file/YAML-validity/large-file hooks.

Nine lint issues were found and fixed (mostly auto-fixed): an unused import, a non-`collections.abc` typing import, `datetime.timezone.utc` → `datetime.UTC` alias, one line-length violation, and import-sort ordering.

```bash
python -m ruff check .   # All checks passed!
```

To enable the git hook locally: `pip install pre-commit && pre-commit install`.

## 3. Dataclasses — no change

Confirmed: staying with `dataclasses`, not moving to Pydantic. Nothing in Milestone 1's validation needs (a handful of `__post_init__` range/presence checks) justifies Pydantic's runtime-validation machinery yet. Revisit only if a later milestone's config surface (e.g. broker-repository options, multi-portfolio settings) grows nested/conditional validation that `__post_init__` genuinely struggles to express clearly.

## 4. Performance benchmarks

`scripts/benchmark.py` generates synthetic portfolios (100/500/1000 holdings) and times `PortfolioEngine.run()` (all 3 calculators) in isolation — no network, no HA. Results recorded in `BENCHMARKS.md`:

| Holdings | Mean (ms) |
|---|---|
| 100 | ~0.3 |
| 500 | ~1.5 |
| 1000 | ~3.0 |

Linear scaling, as expected from O(n)-per-calculator design — no accidental quadratic behavior. This is a **baseline for regression comparison**, not an optimization result; see `BENCHMARKS.md` for what it does and doesn't measure (notably: excludes provider/network I/O, which will dominate real-world coordinator timing by orders of magnitude).

A sanity test (`tests/test_benchmark_harness.py`) confirms the harness itself runs correctly; it does not assert on timing, since CI runner speed varies and a shared runner being slow today shouldn't fail the build.

## 5. Independent engine versioning

`engine/__version__ = "0.1.0"`. Documented in ADR-0007: the engine and the eventual HA integration (Milestone 2's `manifest.json`) version independently, since they change for different reasons — an engine-internal refactor or new calculator doesn't necessarily imply an HA-facing change, and vice versa.

## 6. New ADRs

- **ADR-0006 — Public Entity Stability**: once an entity ID ships in Milestone 2, it's a stable contract; refactor inside the engine, don't rename or repurpose shipped entities. New data ships as new entities, additively.
- **ADR-0007 — Independent Engine Versioning**: covered above.

## Updated validation checklist

- [x] `pytest tests/` passes (22/22 — 20 from Milestone 1 + 2 benchmark-harness sanity tests)
- [x] `mypy` strict, zero issues, scoped to source packages
- [x] `ruff check .` clean
- [x] `BENCHMARKS.md` recorded (100/500/1000 holdings, linear scaling confirmed)
- [x] `engine.__version__ == "0.1.0"`
- [x] ADR-0006 and ADR-0007 written

## Guidance carried into Milestone 2

See `MILESTONE_2_PLAN.md` for the minimal entity surface this review asked
for, recorded now so Milestone 2 starts from an agreed, deliberately small
scope rather than exposing every calculator output as an entity by default.
