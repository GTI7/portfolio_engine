# Home Assistant Compatibility Policy

## Minimum supported Home Assistant version

**HA Core 2025.1** or later.

This is set from what was actually validated (`tests_ha/` runs against `homeassistant==2025.1.4`, the version resolved by `pytest-homeassistant-custom-component` at the time of this milestone — see `MILESTONE_2_5.md`), not chosen arbitrarily. `manifest.json` does not currently declare `"homeassistant"` as a version constraint because HA's manifest schema doesn't support a min-version field directly for custom integrations; this policy document is the source of truth until/unless that changes, and should be checked before assuming a much older HA install will work.

Nothing in this integration deliberately excludes older HA versions — the ceiling is "whatever's actually been tested," not a designed floor. If someone confirms it works on an earlier version, this number can move down; it should never move down without that confirmation.

## Compatibility policy

- **Testing baseline**: `tests_ha/` (Milestone 2.5) is the source of truth for "does this work with HA version X" — it pins a specific `homeassistant` version via `pytest-homeassistant-custom-component`'s own dependency resolution. Bumping that dependency and re-running the suite is how this integration's HA-compatibility gets re-validated going forward, not manual spot-checking.
- **HA API usage**: this integration uses only documented, non-deprecated HA APIs as of the tested version (`DataUpdateCoordinator`, `ConfigEntry`/`OptionsFlow`, `SensorEntity`, `DeviceInfo`, `CoordinatorEntity`, `homeassistant.helpers.redact`). No use of internal (underscore-prefixed) HA internals, which are the usual source of custom-integration breakage across HA releases.
- **Breaking HA releases**: when a new HA release changes behavior this integration depends on (discovered via the CI job described below, or a user report), the fix path is: reproduce against `tests_ha/`, patch, bump the minimum supported version in this document if the fix isn't backward compatible with older HA releases, and note it in release notes (see below).

## Deprecation policy

Applies to anything this integration exposes to users or to Home Assistant itself:

- **Entities** (already covered in detail by `ENTITY_API_POLICY.md` / ADR-0006): additive by default; removal only via a documented migration path, never silently.
- **Config entry data/options schema**: new fields are added with safe defaults so existing entries keep working unmigrated. Removing or renaming a field requires a migration step in `async_setup_entry` (using `ConfigEntry`'s version/minor_version mechanism) that runs automatically on next load — never a manual "delete and re-add the integration" as the only path, except as an absolute last resort, documented as such in release notes.
- **Services** (none exist yet, Milestone 2 scope): once added, same additive-by-default rule applies.
- **Minimum HA version bumps**: raising the floor (dropping support for older HA releases) is itself a breaking change for anyone still on an older release — it gets called out explicitly in release notes, with the reason (e.g. "requires an HA API only available from 2025.6+").

## Release notes for breaking changes

Any release that includes a breaking change (entity removal/rename beyond what ADR-0006 permits, config schema change without an automatic migration, minimum-HA-version bump) must document in its release notes:

1. **What changed** — plainly, not just a diff summary.
2. **Why** — the concrete reason (HA API removal, security issue, correctness bug too costly to migrate around).
3. **What the user needs to do**, if anything — ideally "nothing, it's automatic," but if manual action is required, exact steps.

Non-breaking releases (new entities, new calculators, bug fixes that don't change behavior anyone would have depended on) don't need this level of ceremony — a normal changelog entry is enough.

## Where this lives going forward

This document is the policy. `MILESTONE_2_5.md` records when it was introduced and why. Future milestones update this file directly rather than restating the policy in each milestone's own notes — milestone docs should reference it, not duplicate it.
