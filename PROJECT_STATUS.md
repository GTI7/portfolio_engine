# Project Status

| | |
|---|---|
| **Current Version** | 1.0.1 (integration) · 1.0.0 (engine, unchanged) |
| **Status** | Stable |
| **Development Branch** | `v1.x` |
| **Current Priority** | Manual validation (Recorder/restart/live network) |
| **Known Technical Debt** | `ConfigEntry.runtime_data` migration |
| **Next Planned Release** | v1.0.2 |

## Current priority: manual validation (Recorder/restart/live network)

**The automated part of this closed with v1.0.1's CI setup.** Every milestone since 8 flagged the real-HA-harness suite (`tests_ha/`, 77 tests of real HA Core code, not mocked) as validated only sporadically and by hand — genuine coverage that existed, but never running anywhere on its own. `.github/workflows/tests.yml` now runs it on every push and pull request against `main`, on `ubuntu-latest` (notably, this suite's `homeassistant` dependency assumes a POSIX event loop and never ran on Windows locally — CI is the first environment where all 77 have actually been confirmed green end-to-end, not just "should pass"). See `TESTING.md`'s "Continuous integration" section.

What's left is specifically what `MANUAL_VALIDATION_RUNBOOK.md`'s "Execution Record" documents as still unverified, and CI structurally cannot cover any of it: Recorder long-term statistics rendering over real elapsed time, visual/UI screenshots with real portfolio data, a true host-level process restart, and real network conditions against Yahoo Finance's actual endpoint (as opposed to the harness's mocked responses). None of that gap has closed since it was first documented — it needs a real, persistent Home Assistant instance with file-write access to `config/custom_components/`, which no session so far has had.

If this is being picked up now, the concrete next steps are exactly the ones `MANUAL_VALIDATION_RUNBOOK.md`'s checklist (below the Execution Record) already lays out — install the integration on an actual instance per `docs/user/INSTALLATION.md`, and work through what's still unchecked.

## Known technical debt: `ConfigEntry.runtime_data`

`docs/QUALITY_SCALE.md` has the full self-assessment; this is the one item from it called out here as the actual next-release-relevant debt. Coordinator storage currently uses `hass.data[DOMAIN][entry.entry_id]` (the Milestone 2 pattern) rather than the newer `ConfigEntry.runtime_data` typed-storage convention HA has moved toward. Functionally equivalent today, but migrating touches every file that reads that lookup: `__init__.py`, `services.py` (`_find_coordinator_for_portfolio`), `diagnostics.py`, and `sensor.py`. Not started — Milestone 10 identified it and left it open rather than rushing an invasive, cross-cutting change late in that session without full test coverage behind it.

**Not started in v1.0.1 either** — that release was a targeted patch (Yahoo Finance 401 fix, plus a test-infrastructure cleanup), deliberately scoped away from this. If v1.0.2 is meant to close this out, that's real, scoped work — the four touch points above, each needing its existing test coverage to keep passing unmodified plus new coverage for whatever `runtime_data` typing adds — worth doing as its own deliberate pass rather than folded into a status update. Happy to start on it directly if that's the intent; flagging it as a distinct next step rather than assuming.

## Where the rest of the project stands

- **Engine**: v1.0.0, stable API declaration (no calculation code changed across Milestones 8–10, nor by v1.0.1) — see `engine/__init__.py`'s own docstring.
- **Integration**: v1.0.1, `custom_components/portfolio_engine/` — see `CHANGELOG.md` for the v1.0.1 Yahoo Finance 401 fix.
- **Tests**: 426 total (307 engine, 42 pure-logic integration, 77 real-HA-harness) — `TESTING.md`.
- **Documentation**: contributor-facing docs at the repository root and `docs/`; end-user docs at `docs/user/`; `docs/QUALITY_SCALE.md` for the honest HA Quality Scale self-assessment; `docs/RELEASE_CHECKLIST.md` for what a real GitHub repository still needs before actual HACS publication.
- **Milestone history**: `MILESTONE_1.md` through `MILESTONE_10.md`, each an honest account of what shipped, what was found and fixed along the way, and what was deliberately deferred.
