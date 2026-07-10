# ADR 0007: Version the Portfolio Engine Independently of the HA Integration

**Status:** Accepted
**Date:** 2026-07-09

## Decision

`engine/` carries its own semantic version (`engine.__version__`, starting at `0.1.0`), tracked independently of the Home Assistant custom integration's `manifest.json` version. The engine's version bumps on changes to its own public interface (models, calculator outputs, `PortfolioEngine.run()`'s contract); the integration's version bumps on changes to HA-facing behavior (entities, config flow, services) — the two numbers will diverge, and that's expected, not a bug to reconcile.

## Reason

The entire premise established in Milestone 1 is that `engine/` is a standalone, HA-independent package (ADR-0001 through 0005 all build on that). A package that's genuinely independent needs its own version identity — otherwise "independent" is only true of the code's import graph, not of its release/change process. Independent versioning also gives the ADR-0006 entity-stability guarantee a concrete mechanism: the integration can bump its own version for an entity change while the engine underneath is unchanged, or the engine can gain a new calculator (engine minor version bump) with zero HA-facing change (integration version unchanged) until Milestone 2+ wires it up.

## Alternatives Considered

- **Single version number for the whole project** — rejected; it would force every engine-internal change (a new calculator, a bugfix in `PortfolioCalculator`) to also be framed as an integration release, even when no entity or HA-facing behavior changed, which muddies exactly the boundary Milestone 1 was built to establish.

## Consequences

- `engine/__init__.py` exports `__version__`; this is the number referenced in `MILESTONE_*.md` changelogs and any future `CHANGELOG.md` for the engine specifically.
- The HA integration's `manifest.json` (Milestone 2) will separately declare which engine version range it depends on, the same way any Python package declares a dependency version constraint — this becomes relevant once the engine is packaged for installation rather than vendored directly into `custom_components/`.
- Slight bookkeeping overhead (two version numbers to reason about instead of one), accepted because it's what "independent" was supposed to mean in the first place.
