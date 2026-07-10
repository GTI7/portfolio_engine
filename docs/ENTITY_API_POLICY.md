# Entity API Policy

This operationalizes ADR-0006 (Public Entity Stability) into concrete rules to follow when touching `sensor.py` or adding new platforms. ADR-0006 is the *decision*; this document is the *checklist* for applying it correctly as the integration grows.

## The six entities shipped in Milestone 2 are the current public API

| Entity | Meaning (frozen) |
|---|---|
| `sensor.<portfolio>_value` | Total value = positions + cash, in the portfolio's base currency |
| `sensor.<portfolio>_total_invested` | Sum of cost basis across positions (cash excluded) |
| `sensor.<portfolio>_total_profit` | `value - total_invested` (unrealized gain, cash excluded) |
| `sensor.<portfolio>_roi` | `total_profit / total_invested * 100` — percent, invested-capital basis |
| `sensor.<portfolio>_cash_balance` | `Portfolio.cash_balance`, in base currency |
| `sensor.<portfolio>_positions` | Count as state; full positions table as the `positions` attribute |

## Rules

1. **Prefer adding entities over renaming existing ones.** A new metric (allocation breakdown, dividend income, a risk figure) is a new entity, never a repurposed existing one — even if an existing entity's *name* would arguably fit better. Naming regret is not sufficient reason to rename a shipped entity; open an ADR if you think the cost of living with an imperfect name is actually worse than the migration cost of fixing it.
2. **Preserve entity IDs whenever possible.** Entity IDs derive from `unique_id` + friendly name at first creation and HA does not change them automatically on a name/translation update — don't manually force a rename via the entity registry as part of a routine change. If a `unique_id` scheme itself must change (rare — e.g. multi-portfolio support needing a different key shape), that's a registry migration, not a casual edit; write an ADR first.
3. **Avoid changing state meanings after release.** If `sensor.<portfolio>_roi` ever needs to change from "invested-capital basis" to "total-value basis" (a real, defensible alternative definition), that is a breaking change to what the number *means*, even though the entity ID and unit stay the same. Treat it exactly as if it were a rename: document in release notes, and prefer adding a second entity (`_roi_including_cash`) over redefining the first.
4. **Unit and device class changes are breaking.** Changing `native_unit_of_measurement` or `SensorDeviceClass` on a shipped entity changes how HA's own statistics interpret its history — don't do this without a migration note, since it can silently corrupt long-term statistics continuity for anyone already tracking it.
5. **Document any unavoidable breaking change in release notes** per `COMPATIBILITY_POLICY.md` — what changed, why it was unavoidable, and exactly what the user needs to do (ideally: nothing, via an automatic entity-registry migration).
6. **New platforms follow the same rules from their first release.** When a future milestone adds a `binary_sensor` (e.g. `binary_sensor.<portfolio>_market_open`) or a `number`/`button` entity, it becomes part of this same frozen contract the moment it ships — there's no "grace period" where a newly-shipped entity is still considered mutable.
7. **Every entity requires a contract entry before it's considered shipped.** `docs/ENTITY_CONTRACTS.md` documents purpose, state meaning, unit, state class, device class, intended automation use, and intended dashboard use for every entity — filled in as part of the same change that adds the entity, not as a follow-up. This is what keeps rules 1–6 enforceable in practice: you can't judge whether a later change is "additive" or "breaking" against an entity whose intended meaning was never written down.

## What this does NOT freeze

- **Internal engine calculations** (`engine/`, `Calculator` implementations) — ADR-0006 explicitly scopes stability to *exposed entities*, not the engine's internal interfaces. `Calculator.calculate()`'s signature already changed once (ADR-0008) with no user-facing consequence, precisely because that boundary is deliberately kept free to evolve.
- **Diagnostics payload shape** (`diagnostics.py`) — useful to keep reasonably stable for anyone scripting against downloaded diagnostics, but it's explicitly a debugging aid, not the integration's API surface, and isn't held to the same bar.
- **Attribute contents on the `positions` entity** — the top-level entity (`sensor.<portfolio>_positions`) and its existence are stable per the rules above, but the *shape* of each item in the `positions` attribute list is expected to gain fields over time (e.g. sector/region once those land) — additive changes there are fine without being treated as breaking, since dashboards reading it should already tolerate unknown extra keys. Removing or renaming a field within that shape, however, is breaking by the same logic as rule 3.
