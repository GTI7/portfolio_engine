# Portfolio Engine — v1.0.1

[![Tests](https://github.com/GTI7/portfolio_engine/actions/workflows/tests.yml/badge.svg)](https://github.com/GTI7/portfolio_engine/actions/workflows/tests.yml)

**v1.0.1** (integration) — a targeted Yahoo Finance 401 fix plus a
test-infrastructure cleanup, not a milestone. The engine itself remains
v1.0.0, unchanged since Milestone 10 (see ADR-0007 for why the two are
versioned independently). See [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
for the current release, active branch, priority, and known technical
debt at a glance, and [`CHANGELOG.md`](CHANGELOG.md) for exactly what
changed in v1.0.1.

**Development history:** Milestone 1: the HA-independent calculation
core. Milestone 2: wiring it into Home Assistant. Milestone 2.5:
real-harness validation. Milestone 3: currency support. Milestone 4:
transaction history. Milestone 5: money-weighted return. Milestone 6:
snapshot engine + time-weighted return. Milestone 7: portfolio
analytics. Milestone 8: Home Assistant UX & production readiness.
Milestone 9: a read-only broker import framework. Milestone 10:
production polish — configuration UX fixes, backup/export, HA Quality
Scale self-assessment, HACS readiness, richer dashboard cards —
culminating in the v1.0.0 release. See `MILESTONE_10.md` and
`docs/QUALITY_SCALE.md` for exactly what that does and doesn't mean.

**New to using (not building) this integration?** Start at
[`docs/user/README.md`](docs/user/README.md) instead of here — this README
and everything else at the repository root is for people working on the
integration's code, not people just running it.

See `MILESTONE_1.md` through `MILESTONE_10.md` (plus `MILESTONE_4_SPEC.md`,
`MILESTONE_7_DESIGN.md`) for what's in each. See `docs/adr/` (13 ADRs) for
architectural decisions, `docs/QUALITY_SCALE.md` for an honest HA
Integration Quality Scale self-assessment, `docs/RELEASE_CHECKLIST.md` for
what's still needed to actually publish this (a real GitHub repository),
`docs/COMPATIBILITY_POLICY.md` / `docs/ENTITY_API_POLICY.md` for governance
policy, `docs/ENTITY_CONTRACTS.md` for the documented contract behind every
shipped entity (15), `CHANGELOG.md` for what changed release over release,
and `TESTING.md` for how the test categories fit together.

```
portfolio_engine/
├── engine/                          # standalone HA-independent package (v1.0.0)
├── repositories/                    # data retrieval — no calculation (ADR-0001)
├── providers/                       # market data — no portfolio data (ADR-0002)
├── importers/                       # broker export -> Transaction[] (ADR-0013)
├── custom_components/portfolio_engine/   # the Home Assistant integration (v1.0.1)
│   ├── manifest.json, const.py
│   ├── config_flow.py                # + multi-entry support + reconfigure flow (Milestone 10)
│   ├── coordinator.py
│   ├── __init__.py                   # + export service registration/deregistration
│   ├── services.py                   # import_transactions + export_portfolio_data
│   ├── services.yaml
│   ├── import_report_store.py
│   ├── sensor.py                     # 15 entities, PARALLEL_UPDATES declared (Milestone 10)
│   ├── diagnostics.py
│   ├── update_logic.py
│   ├── sensor_mapping.py
│   ├── store_snapshot_repository.py
│   ├── translations/en.json, strings.json
│   └── engine/, repositories/, providers/, importers/   # vendored copies
├── dashboards/
│   └── portfolio_engine_dashboard.yaml   # 7 views, now with gauge cards (Milestone 10)
├── sample_data/demo_portfolio/holdings.yaml       # for engine-level tests
├── sample_investments/demo_portfolio/holdings.yaml # for trying the real integration
├── tests/                           # 305 tests — the engine, pytest + pytest-asyncio
├── tests_integration/               # 38 tests — the integration's pure-logic layer
├── tests_ha/                        # 77 tests — real HA harness
├── scripts/
│   ├── benchmark.py                  # 2D baseline: holdings count + snapshot-history length
│   └── setup_ha_test_env.sh          # one-time setup for tests_ha/
├── docs/
│   ├── adr/                          # 13 ADRs + template
│   ├── architecture/                 # the 3 architecture design docs (v1-v3)
│   ├── user/                         # end-user documentation
│   │   ├── README.md, INSTALLATION.md, GETTING_STARTED.md, DASHBOARDS.md,
│   │   │   BROKER_IMPORT.md, BACKUP_EXPORT.md, TROUBLESHOOTING.md, FAQ.md
│   ├── QUALITY_SCALE.md              # NEW (Milestone 10): honest HA Quality Scale self-assessment
│   ├── RELEASE_CHECKLIST.md          # NEW (Milestone 10): what's left to actually publish
│   ├── COMPATIBILITY_POLICY.md
│   ├── ENTITY_API_POLICY.md
│   └── ENTITY_CONTRACTS.md
├── hacs.json                         # NEW (Milestone 10)
├── LICENSE                           # NEW (Milestone 10): MIT
├── BENCHMARKS.md                     # + benchmark-noise investigation (Milestone 10)
├── MANUAL_VALIDATION_RUNBOOK.md
├── CHANGELOG.md
├── TESTING.md
├── MILESTONE_1.md, MILESTONE_1_ADDENDUM.md, MILESTONE_2.md,
│   MILESTONE_2_PLAN.md, MILESTONE_2_5.md, MILESTONE_3.md,
│   MILESTONE_4_SPEC.md, MILESTONE_4.md, MILESTONE_5.md, MILESTONE_6.md,
│   MILESTONE_7_DESIGN.md, MILESTONE_7.md, MILESTONE_8.md, MILESTONE_9.md,
│   MILESTONE_10.md
├── pyproject.toml                    # version, mypy, ruff config
├── .pre-commit-config.yaml
├── requirements.txt, requirements-test.txt, requirements-ha-test.txt
└── pytest.ini
```

Quick start:

```bash
# Fast path: engine + integration pure-logic tests
pip install -r requirements.txt -r requirements-test.txt
python -m pytest tests/ tests_integration/ -v   # 343 passed
python -m ruff check . custom_components/ importers/
python -m mypy                                   # engine/repositories/providers/importers

# Real Home Assistant harness (separate, heavier — see MILESTONE_2_5.md)
./scripts/setup_ha_test_env.sh
.ha_test_venv/bin/python -m pytest tests_ha/ -v   # 77 passed
```

To try the real Home Assistant integration on a live instance, see
`docs/user/INSTALLATION.md` for setup and `MANUAL_VALIDATION_RUNBOOK.md`
for the validation checklist and its honest execution record. To actually
publish this (GitHub repository, HACS listing), see
`docs/RELEASE_CHECKLIST.md`.










