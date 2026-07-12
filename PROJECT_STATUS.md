# Project Status

| | |
|---|---|
| **Current Version** | 1.3.0 (integration) · 1.0.0 (engine, unchanged) |
| **Status** | Stable |
| **Development Branch** | `v1.x` |
| **Current Priority** | Manual validation (Recorder/restart/live network) |
| **Known Technical Debt** | `ConfigEntry.runtime_data` migration |
| **Next Planned Release** | Not yet decided — `ConfigEntry.runtime_data` migration remains the leading candidate |

## Milestone 13 — Dashboard & User Experience

**Status:** Released as v1.3.0. Automated verification (fast suite, `ruff`, vendored-copy sync) and documentation/architecture review are complete; this release is what makes real-world Home Assistant validation possible in the first place (the project is installed via HACS from GitHub Releases, not `main` — see `docs/testing/MILESTONE_13_MANUAL_VALIDATION.md`'s checklist, still to be run against a real instance now that this release exists to install). See `MILESTONE_13_DESIGN.md` and ADR-0019 for the full design.

**Phase 1 — Dashboard native-cards rework:**
- `dashboards/portfolio_engine_dashboard.yaml` rebuilt around native Home Assistant cards (`entities`, `gauge`, `history-graph`, `statistics-graph`) wherever the platform permits, reserving `markdown` only for the Holdings/Transactions tables, a couple of nested-attribute summaries, and genuinely conditional/static text.
- Every entity ID defined exactly once via a YAML anchor in the Overview view; every other card references it by alias — a small, one-time, clearly-documented edit in exchange for full native card behavior (click-to-more-info, native theming, real gauges/charts), see ADR-0019.
- Reorganized from 7 views to 6 (Overview, Holdings, Performance, Transactions, Analytics, Administration — merging the old Health + Import/Backup views), each framed around the one question it answers.

**Phase 2 — Backend gaps closed:**
- `sensor.<portfolio>_day_change` — exposes `PerformanceCalculator`'s already-computed day-over-day change; previously nothing surfaced it.
- `sensor.<portfolio>_allocation` — exposes `AllocationCalculator`'s already-computed by-type breakdown (stocks/ETFs/cash/...); previously nothing surfaced it. Both new entities added minimally to the dashboard, no reorganization.
- `docs/ENTITY_CONTRACTS.md` gained entries for both new entities, plus the pre-existing missing entry for `sensor.<portfolio>_last_import` (Milestone 9, a documentation-only gap).
- Fixed: `apply_import`/`create_portfolio` (Milestone 12) were never deregistered on last-entry-unload — a real gap, not just theoretical (the tests asserting correct behavior already existed but couldn't run locally on this Windows dev environment).

**Tests:**
- Fast suite (`tests/` + `tests_integration/`): 382/382 passing.
- `tests_ha/`: 102 tests collected cleanly (import-valid); execution still blocked locally by the documented Windows `ProactorEventLoop` limitation. Runs green in CI (`ubuntu-latest`).
- `ruff check` clean; `tests/test_vendored_copy_sync.py` passes (no vendored files touched this milestone — `sensor.py`/`sensor_mapping.py`/`__init__.py` are HA-only, not vendored).
- No automated coverage exists for the dashboard YAML itself (not exercised by `tests_ha/`) — verified instead by a throwaway Jinja dry-run render against mocked two-portfolio data during development. Real-instance validation (`docs/testing/MILESTONE_13_MANUAL_VALIDATION.md`) follows this release rather than gating it — HACS installs from GitHub Releases, so this release is the prerequisite for that validation, not a consequence of it.

**Next milestone:** TBD; `ConfigEntry.runtime_data` migration remains the leading candidate (see "Known technical debt" below).

## Current priority: manual validation (Recorder/restart/live network)

**The automated part of this closed with v1.0.1's CI setup.** Every milestone since 8 flagged the real-HA-harness suite (`tests_ha/`, 77 tests of real HA Core code, not mocked) as validated only sporadically and by hand — genuine coverage that existed, but never running anywhere on its own. `.github/workflows/tests.yml` now runs it on every push and pull request against `main`, on `ubuntu-latest` (notably, this suite's `homeassistant` dependency assumes a POSIX event loop and never ran on Windows locally — CI is the first environment where all 77 have actually been confirmed green end-to-end, not just "should pass"). See `TESTING.md`'s "Continuous integration" section.

What's left is specifically what `MANUAL_VALIDATION_RUNBOOK.md`'s "Execution Record" documents as still unverified, and CI structurally cannot cover any of it: Recorder long-term statistics rendering over real elapsed time, visual/UI screenshots with real portfolio data, a true host-level process restart, and real network conditions against Yahoo Finance's actual endpoint (as opposed to the harness's mocked responses). None of that gap has closed since it was first documented — it needs a real, persistent Home Assistant instance with file-write access to `config/custom_components/`, which no session so far has had.

If this is being picked up now, the concrete next steps are exactly the ones `MANUAL_VALIDATION_RUNBOOK.md`'s checklist (below the Execution Record) already lays out — install the integration on an actual instance per `docs/user/INSTALLATION.md`, and work through what's still unchecked.

## Known technical debt: `ConfigEntry.runtime_data`

`docs/QUALITY_SCALE.md` has the full self-assessment; this is the one item from it called out here as the actual next-release-relevant debt. Coordinator storage currently uses `hass.data[DOMAIN][entry.entry_id]` (the Milestone 2 pattern) rather than the newer `ConfigEntry.runtime_data` typed-storage convention HA has moved toward. Functionally equivalent today, but migrating touches every file that reads that lookup: `__init__.py`, `services.py` (`_find_coordinator_for_portfolio`), `diagnostics.py`, and `sensor.py`. Not started — Milestone 10 identified it and left it open rather than rushing an invasive, cross-cutting change late in that session without full test coverage behind it.

**Not started in v1.0.1 through v1.3.0 either** — v1.0.1 was a targeted patch (Yahoo Finance 401 fix, plus a test-infrastructure cleanup), v1.1.0 (Milestone 11, Asset Discovery) was scoped entirely to a new, additive provider + service, v1.2.0 (Milestone 12, Portfolio Import & Assisted Setup) added a new write path and two services, and v1.3.0 (Milestone 13, Dashboard & User Experience) reworked the dashboard and closed two backend entity gaps — all deliberately away from this. That's real, scoped work — the four touch points above, each needing its existing test coverage to keep passing unmodified plus new coverage for whatever `runtime_data` typing adds — worth doing as its own deliberate pass rather than folded into a status update. Happy to start on it directly if that's the intent; flagging it as a distinct next step rather than assuming.

## Known issue: quotes valued at zero on a failed fetch (flagged, not fixed)

Discovered 2026-07-12 during a live-dashboard UX refinement pass (Overview view) against a real HA instance — not investigated or fixed as part of that pass, per explicit scope (dashboard/presentation only).

**Observed:** `sensor.<portfolio>_value`'s Recorder history oscillates by several hundred currency units every ~15 minutes, in lockstep with `sensor.<portfolio>_positions`' `symbols_missing_quotes` attribute intermittently listing certain symbols (two ETFs, in the observed case). The `Value Trend` history-graph on the Overview dashboard renders this as a flapping, untrustworthy-looking chart even though the chart itself is correct — the underlying data is unstable.

**Root cause, confirmed by reading (not modifying) the code:** `engine/portfolio_engine.py`'s `build_positions` resolves each holding's price as `quote.price if quote else 0.0` (`quote = quotes.get(holding.symbol)`, ~lines 48–49). When a price provider's quote fetch misses for a symbol on a given refresh, that holding's price — and therefore its `market_value`/`market_value_base` — is treated as exactly `0.0` for that cycle rather than carrying forward the last known-good quote. The next successful refresh brings the value back, producing the oscillation. This likely also relates to the small `avg_price` reconciliation discrepancy observed for the same symbol on the same instance.

**Question for a future investigation:** should a missed quote fetch keep falling back to `0.0` (current, confirmed behavior above), or should the position retain its last known-good quote until a fresh one is available? The current behavior makes a transient quote-provider hiccup look like a real, sudden change in portfolio value.

**Scope note:** this is a computation-layer question in `engine/portfolio_engine.py`, to be evaluated as its own deliberate change with its own tests — not folded into dashboard work.

## Where the rest of the project stands

- **Engine**: v1.0.0, stable API declaration (no calculation code changed across Milestones 8–13, nor by v1.0.1's/v1.1.0's/v1.2.0's/v1.3.0's own HA-facing additions — `AllocationCalculator`/`PerformanceCalculator` used by Milestone 13's two new entities have both existed, unchanged, since Milestones 1/3) — see `engine/__init__.py`'s own docstring.
- **Integration**: v1.3.0 (current release), `custom_components/portfolio_engine/` — see `CHANGELOG.md` for the v1.3.0 Dashboard & User Experience milestone, the v1.2.0 Portfolio Import & Assisted Setup milestone, the v1.1.0 Asset Discovery milestone, and the earlier v1.0.1 Yahoo Finance 401 fix.
- **Tests**: 484 total (332 engine, 50 pure-logic integration, 102 real-HA-harness) — `TESTING.md`.
- **Documentation**: contributor-facing docs at the repository root and `docs/`; end-user docs at `docs/user/` (including `PORTFOLIO_IMPORT_AND_SETUP.md`, `ASSET_DISCOVERY.md`, and the rewritten `DASHBOARDS.md`); `docs/QUALITY_SCALE.md` for the honest HA Quality Scale self-assessment; `docs/RELEASE_CHECKLIST.md` for what a real GitHub repository still needs before actual HACS publication.
- **Milestone history**: `MILESTONE_1.md` through `MILESTONE_10.md`, plus `MILESTONE_11_DESIGN.md` (Asset Discovery), `MILESTONE_12_DESIGN.md` (Portfolio Import & Assisted Setup), and `MILESTONE_13_DESIGN.md` (Dashboard & User Experience), each an honest account of what shipped, what was found and fixed along the way, and what was deliberately deferred.
