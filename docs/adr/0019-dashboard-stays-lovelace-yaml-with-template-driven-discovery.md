# ADR 0019: Dashboards Stay Plain Lovelace YAML — Zero-Config Achieved via Jinja Auto-Discovery, Not a Custom Frontend Strategy

**Status:** Proposed
**Date:** 2026-07-11

## Decision

Portfolio Engine's dashboard remains a plain Lovelace YAML package (`dashboards/portfolio_engine_dashboard.yaml`, evolved from the one already shipped) — no custom card, no custom Dashboard Strategy, no frontend JS resource, no build tooling. Milestone 13 replaces the package's hardcoded `sensor.demo_portfolio_*` entity IDs with Jinja templates that discover entities at render time via HA's built-in `integration_entities('portfolio_engine')` and `device_id(...)` template functions, grouped per device (one device per portfolio, per the existing `_PortfolioEntityBase.device_info` pattern). This makes the package **import-once, edit-never** — it auto-scales to however many portfolios are configured, including one added after the dashboard was first imported, with no find-and-replace step.

A genuine custom Dashboard Strategy (a frontend-registered `strategy:` resource, requiring a JS bundle, `www/` resource registration, and ongoing frontend build tooling this project has never needed) is explicitly **not** adopted for this milestone.

## Reason

Every prior technology choice in this project has favored the smallest mechanism that satisfies the actual requirement over a more powerful one held in reserve (ADR-0002's provider-interface minimalism, ADR-0004's "start with a minimal calculator set", ADR-0005 deferring event-driven processing, ADR-0013 reusing `Transaction.id` instead of adding a field). A custom frontend strategy is a materially larger commitment than this project has ever taken on: it introduces a new artifact type (bundled JS), a new registration surface (`frontend.add_extra_js_url` or a `www/` resource + manual dashboard resource registration by the user), and a new failure mode (a broken frontend resource can silently blank a dashboard, with none of this project's existing test tooling able to catch it — `tests_ha/` verifies backend entity/service behavior, not rendered Lovelace output).

The discovery I made while reviewing the already-shipped package is that HA's **built-in** Jinja template functions already solve the actual pain point (manual find-and-replace of `demo_portfolio`) without any of that cost: `integration_entities('portfolio_engine')` returns every entity this integration owns, across every config entry/device, and `device_id(entity_id)` groups them by portfolio. A markdown/template card iterating these can render one section per configured portfolio automatically — a second portfolio, added later via `create_portfolio` or the guided Config Flow (Milestone 12), simply appears on the next dashboard load, with zero editing. This gets the actual outcome "zero-configuration" was asking for, using only core Lovelace card types the existing package already restricts itself to.

## Alternatives Considered

- **A real custom Dashboard Strategy (frontend JS resource).** Rejected for this milestone — solves the same problem the Jinja-discovery approach already solves, at a much higher ongoing cost (new build/test/distribution surface this project has no precedent or tooling for). Not ruled out permanently: if the Jinja-based package's per-view Jinja logic grows unwieldy as more portfolios/views are added, revisit. Flagged as a future enhancement, not a rejected idea.
- **Keep the current find-and-replace model as-is.** Rejected — directly contradicts this milestone's own "minimal manual editing" and "scale to multiple portfolios" goals, and the fix (built-in Jinja functions) is essentially free.
- **A Python-side dashboard *generator*** — a service or script that reads configured portfolios and emits a ready-to-paste YAML file with entity IDs already substituted. Rejected as unnecessary once the Jinja-discovery approach works: it would solve the exact same problem the template functions already solve, but by adding a new service/script this project would have to build, test, and maintain, for an outcome the dashboard file can already achieve entirely on the frontend side, at render time, with no Python code at all.
- **HA's built-in auto-generated "Overview" dashboard** (every entity grouped by device/area automatically, zero setup). Considered as a genuine zero-effort fallback — it already exists today with no work at all — but it's generic (no curated grouping into Overview/Holdings/Performance/etc., no gauges, no computed markdown tables) and isn't a substitute for a curated experience. Worth mentioning to users in documentation as "what you get before importing the real dashboard," not as the deliverable itself.

## Consequences

- The dashboard package remains a single YAML file, importable via HA's existing "Raw configuration editor" flow (`docs/user/DASHBOARDS.md`'s existing instructions), just without the find-and-replace step.
- Every view's Jinja must be written against `integration_entities('portfolio_engine')` + `device_id(...)` groupings rather than literal `sensor.demo_portfolio_*` names — a real, non-trivial rewrite of every existing view's templates (this is Milestone 13's Phase 1 work, not a small tweak).
- No new frontend build/test/distribution surface is introduced — `tests_ha/` and the rest of this project's testing conventions remain unaffected; dashboard correctness continues to be verified by hand against a real HA instance (per `MANUAL_VALIDATION_RUNBOOK.md`'s existing scope), not by the automated suite.
- A genuine custom Dashboard Strategy remains available as a future option if the Jinja-discovery approach's per-view logic becomes unmanageable — this ADR documents why it wasn't chosen now, not why it could never be chosen.
- Multi-portfolio users get a materially better experience than today (no per-portfolio dashboard duplication needed) even though the *integration* itself is still single-portfolio-per-config-entry under the hood — the dashboard's multi-portfolio support arrives ahead of, and independent from, any future multi-portfolio engine work.
