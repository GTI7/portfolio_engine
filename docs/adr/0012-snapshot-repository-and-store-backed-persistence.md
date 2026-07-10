# ADR 0012: Separate SnapshotRepository, with the First Store-Backed Persistence

**Status:** Accepted
**Date:** 2026-07-09

## Decision

Snapshots are stored via a new, separate `SnapshotRepository` interface — not folded into `PortfolioRepository`. The engine-level package (`repositories/`) defines the interface plus an `InMemorySnapshotRepository` reference implementation used for engine unit tests. The production implementation, `StoreSnapshotRepository`, lives only in `custom_components/portfolio_engine/` and uses Home Assistant's `homeassistant.helpers.storage.Store` helper — this is the first time this project's persistence actually lands where ADR-0003 said it eventually would, rather than in a hand-editable YAML file.

`Portfolio.snapshots` is populated by `update_logic.py` after reading both `PortfolioRepository` and `SnapshotRepository` separately and attaching the result — not by `PortfolioRepository.async_get_portfolios()` itself, unlike `Portfolio.transactions` (Milestone 4).

## Reason

**Why a separate interface, not an extension of `PortfolioRepository`:** `PortfolioRepository` retrieves user-declared configuration (`holdings.yaml`) and, per Milestone 4, historical events a user or broker feed writes (`transactions.yaml`). Snapshots are neither — they're *generated* by this integration itself, on a schedule, as a byproduct of normal operation, never hand-authored. Mixing "config/events a human or external system produces" with "operational data this system produces about itself" into one interface would blur a distinction that matters: snapshots can be regenerated (imperfectly, but not catastrophically) if lost, in a way holdings and transactions can't be reconstructed if a user's records are gone. Different data has different backup/loss tolerance, which argues for different storage decisions, which argues for different interfaces.

**Why Store now, and not another YAML file matching Milestone 4's `transactions.yaml` pattern:** ADR-0003 (Milestone 1) already decided this in principle — Recorder is wrong for financial history because of its purge policy, and `Store` is the right mechanism, but building it was deferred until there was an actual snapshot mechanism to attach it to. That trigger is now. Unlike `transactions.yaml` (hand-edited, low write frequency, a human plausibly wants to read or edit it directly), snapshots are written automatically, potentially daily, indefinitely, by the integration itself — nobody hand-authors a snapshot. A YAML file that's never meant to be hand-edited and grows forever is exactly the case `Store`'s JSON-backed, atomic-write persistence is suited for and a flat YAML file is not (no external editing expectation to preserve, unbounded append growth, needs to survive HA restarts reliably without file-corruption risk from a crash mid-write).

**Why `Portfolio.snapshots` is attached by `update_logic.py`, not the repository:** `PortfolioRepository.async_get_portfolios()`'s contract (Milestone 1) is "return complete `Portfolio` objects from one read." Extending that same method to also reach into a *second*, unrelated repository (`SnapshotRepository`) to populate one field would couple two independent interfaces at exactly the layer (`YamlRepository`) that has no reason to know `SnapshotRepository` exists — `YamlRepository` doesn't run inside Home Assistant and shouldn't need to. `update_logic.py` (already the place that fetches quotes and FX rates from independent providers and assembles the full picture, per Milestone 3) is the natural, already-established place to do the same for snapshots.

## Alternatives Considered

- **Extend `PortfolioRepository` with snapshot methods, matching the `transactions.yaml` precedent exactly** — rejected: conflates config/event data with self-generated operational data, and forces `YamlRepository` (which has no business knowing about Home Assistant's `Store`) to either implement Store-backed snapshot storage itself or leave `supports_snapshots` permanently `False`, an awkward asymmetry with how `supports_transactions` works.
- **A `snapshots.yaml` file, matching `transactions.yaml`'s pattern** — rejected per the reasoning above: no hand-editing use case, unbounded growth, and it would mean building a second thing (a YAML-based mechanism) now, on the explicit understanding it should eventually migrate to `Store` anyway — better to build the real thing once, now that there's a concrete reason to.
- **Have `PortfolioRepository.async_get_portfolios()` accept an optional `SnapshotRepository` and populate `snapshots` internally** — rejected: still couples the two interfaces at the wrong layer, just via a parameter instead of a hardcoded dependency; `update_logic.py` composing them at the call site (like it already does for prices and FX) is simpler and doesn't touch `PortfolioRepository`'s contract at all.

## Consequences

- The engine (`repositories/`, `engine/`) remains fully HA-independent and testable without `homeassistant` installed — `InMemorySnapshotRepository` exercises the interface's ordering/dedup/migration-safety behavior in the standalone test suite; `StoreSnapshotRepository`'s actual `Store` interaction is tested only in `tests_ha/`, which is exactly where an HA-specific storage mechanism belongs.
- `update_logic.py`'s signature grows one parameter (`snapshot_repository`), the first change to that function's signature since Milestone 3's `currency_provider` addition — a real, visible change, not hidden inside an unrelated method.
- This is the concrete precedent for any future data that's self-generated rather than user/external-declared (e.g. a future audit log, computed-metric cache): separate repository interface, `Store`-backed in the HA layer, composed at the `update_logic.py` call site — not bolted onto `PortfolioRepository`.
