# Milestone 13 Manual Validation (Real Home Assistant Instance)

**This checklist gates the version bump.** Per `PROJECT_STATUS.md`'s Milestone 13 status section, `custom_components/portfolio_engine/manifest.json` stays at `1.2.0` until every item below is checked off against a real, persistent Home Assistant instance — not until then does the manifest move to `1.3.0` and this milestone become releasable. This mirrors `MANUAL_VALIDATION_RUNBOOK.md`'s existing convention (automated coverage first, real-instance confirmation as its own explicit gate), scoped specifically to what Milestone 13 changed: the dashboard's native-cards rework (YAML anchors, gauges, history/statistics graphs, mobile layout) and the two new entities plus the service-unload fix.

Nothing below can be verified in the development environment this milestone was built in — no live HA instance with file-write access to `config/custom_components/` was available (the same standing constraint `MANUAL_VALIDATION_RUNBOOK.md` already documents). What *was* possible locally — YAML structural validity, Jinja template syntax, and a full mock-data render of every markdown card's template against two synthetic portfolios — was done during development and is not repeated here; this checklist is specifically the remainder that needs a real instance.

## Setup

Two scenarios matter for this milestone specifically — run both, not just one:

**A. Fresh install:**
1. Copy `custom_components/portfolio_engine/` into `<ha_config>/custom_components/`.
2. Copy `sample_investments/demo_portfolio/` into `<ha_config>/investments/demo_portfolio/` (or your own holdings) — ideally set up **two** portfolio folders for the multiple-portfolios checks below.
3. Restart Home Assistant, then add the integration (Settings → Devices & Services → Add Integration → "Portfolio Engine").

**B. Upgrade from v1.2.0:**
1. Start from a Home Assistant instance already running Portfolio Engine v1.2.0 (the currently-released version — Milestone 12's `apply_import`/`create_portfolio` services included, but *before* this milestone's changes).
2. Overwrite `custom_components/portfolio_engine/` with this milestone's version.
3. Restart Home Assistant. Do **not** remove and re-add the config entry — the point of this scenario is confirming an in-place upgrade works, not a fresh setup.

## Release acceptance checklist

### Upgrade from v1.2.0
- [ ] After overwriting the integration files and restarting (Setup B above), the existing config entry loads without error — no "not ready," no traceback in Settings → System → Logs.
- [ ] All pre-existing entities keep their exact entity IDs and current values across the upgrade (spot-check a few against what they showed under v1.2.0 before upgrading).
- [ ] The two new entities (`sensor.<portfolio>_day_change`, `sensor.<portfolio>_allocation`) appear automatically after the restart, with no manual step required.
- [ ] Any dashboard already imported under v1.2.0 (the old, hardcoded-entity-ID version or an earlier auto-discovering version) still renders without error — confirms `ADR-0006`'s entity-ID stability guarantee actually held across this change, not just in theory.

### Dashboard import
- [ ] Follow `docs/user/DASHBOARDS.md`'s import steps exactly (paste into the Raw configuration editor) against a real portfolio with real data.
- [ ] All 6 views (Overview, Holdings, Performance, Transactions, Analytics, Administration) load without a Lovelace configuration error.
- [ ] Every markdown card's Jinja resolves without a visible template error (no raw `{{ }}`/`{% %}` text, no "Error rendering template" card).

### YAML anchors
- [ ] Edit only the Overview view's anchor lines (find-and-replace the placeholder portfolio ID) and confirm every other view's native cards — which reference those same anchors — pick up the correct entity automatically, with no other edits made.
- [ ] Confirm the six markdown cards' own `{% set portfolio_id = ... %}` lines were also updated by the same find-and-replace pass (per `docs/user/DASHBOARDS.md`'s "six remaining literal references" section) and that their content matches the same portfolio as every native card.

### Native gauges
- [ ] Performance view's ROI gauge renders as a real native gauge (needle, colored severity zones), not a broken card.
- [ ] Holdings view's concentration gauge renders correctly and its severity coloring (green/yellow/red at the documented thresholds) matches the entity's actual value.
- [ ] Tapping either gauge opens the entity's real more-info dialog (native click-through — the specific capability this milestone traded a fully-automatic dashboard for; confirm it's actually there).

### History graph
- [ ] Overview's Value Trend `history-graph` card renders a real chart using Recorder history for `sensor.<portfolio>_value`, populated with actual historical data (may need the instance to have run for a while, or seed Recorder history for the test).

### Statistics graph
- [ ] Performance's ROI Trend `statistics-graph` card renders using long-term statistics for `sensor.<portfolio>_roi`, not just raw history — confirm it looks meaningfully different from a plain history graph once enough statistics have accumulated.

### New entities
- [ ] `sensor.<portfolio>_day_change` shows a plausible value that changes as quotes update, and is never stuck at `unknown` (per its contract — always a concrete number).
- [ ] `sensor.<portfolio>_allocation` shows the correct largest-group percentage for your real portfolio's actual composition, and its `allocation` attribute (Developer Tools → States) lists every group (stocks/ETFs/cash/etc.) with plausible values summing to ~100%.
- [ ] Both entities' friendly names ("Day Change", "Allocation") display correctly — confirms `strings.json`/`translations/en.json` wiring, not just the raw `translation_key`.

### Multiple portfolios
- [ ] With two portfolios configured (two config entries), confirm each gets its own device (Settings → Devices & Services → Portfolio Engine) and its own complete set of entities, correctly separated — no cross-contamination of one portfolio's values into the other's entities.
- [ ] Duplicate the dashboard's views for the second portfolio (per `docs/user/DASHBOARDS.md`'s "Multiple portfolios" section — new anchor names, e.g. `&value2`) and confirm both portfolios' cards render correctly side by side with no anchor collisions.

### Service unload behavior
- [ ] With `apply_import`/`create_portfolio` both visible in Developer Tools → Actions while a config entry is loaded, remove the **last** remaining Portfolio Engine config entry, then confirm both services disappear from Developer Tools → Actions (not just the platform-specific ones) — this is the specific fix this milestone made; confirm it actually works against a real instance, not just in the test harness.
- [ ] With more than one config entry configured, remove one (not the last) and confirm the services **remain** registered (they're domain-level, shared across entries) — the fix shouldn't have made cleanup too aggressive.

### Mobile layout
- [ ] View the dashboard on an actual phone (or the browser's device-emulation mode at minimum) and confirm: view tabs collapse into the Companion App's normal mobile navigation, the holdings/transactions markdown tables are usable (scroll horizontally if needed, not truncated unreadably), and the gauges/history/statistics graphs resize sensibly rather than overflowing the screen.

## Recording results

Once run, note the HA Core version tested against and the date in `docs/COMPATIBILITY_POLICY.md`'s "Minimum supported Home Assistant version" section if it differs from what's there, and file any bugs found before treating this checklist — and therefore Milestone 13 — as fully closed. Once every box above is checked, bump `custom_components/portfolio_engine/manifest.json` to `1.3.0`, convert `CHANGELOG.md`'s Milestone 13 entry from its current "in progress" framing to a proper `integration 1.2.0 → 1.3.0` versioned entry, and proceed with the normal tag/release process.
