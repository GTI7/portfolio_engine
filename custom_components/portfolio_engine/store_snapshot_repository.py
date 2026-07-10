"""Store-backed SnapshotRepository - the production implementation, HA-
specific per ADR-0012 (docs/adr/0012-snapshot-repository-and-store-backed-
persistence.md). Uses homeassistant.helpers.storage.Store, HA's standard
JSON-backed, atomic-write persistence mechanism, rather than a hand-edited
YAML file - snapshots are self-generated, never hand-authored, and grow
indefinitely, which is exactly the case Store is suited for.

Not vendored into the standalone engine/repositories/ packages (unlike
YamlRepository) - this class genuinely cannot exist without Home Assistant,
so it lives only here and is tested only in tests_ha/.
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .engine.models import Snapshot
from .repositories.snapshot_base import SnapshotRepository

STORAGE_VERSION = 1


class StoreSnapshotRepository(SnapshotRepository):
    """One Store file per config entry (keyed by `entry_id`), holding every
    portfolio's snapshots that entry has ever generated - `entry_id` scoping
    avoids collisions if a future milestone allows multiple config entries.
    """

    name = "store"

    def __init__(self, hass: HomeAssistant, entry_id: str):
        self._store: Store[dict[str, list[dict[str, Any]]]] = Store(
            hass, STORAGE_VERSION, f"portfolio_engine_snapshots_{entry_id}"
        )

    async def async_get_snapshots(self, portfolio_id: str) -> list[Snapshot]:
        data = await self._store.async_load() or {}
        raw = data.get(portfolio_id, [])
        snapshots = [Snapshot.from_dict(d) for d in raw]
        # Chronological order, id as a deterministic tiebreak - same
        # convention as InMemorySnapshotRepository (repositories/, engine
        # unit tests) so both implementations of this interface behave
        # identically from a caller's perspective.
        return sorted(snapshots, key=lambda s: (s.timestamp, s.id))

    async def async_append_snapshot(self, snapshot: Snapshot) -> None:
        data = await self._store.async_load() or {}
        existing = data.setdefault(snapshot.portfolio_id, [])
        if any(d["id"] == snapshot.id for d in existing):
            raise ValueError(
                f"{snapshot.portfolio_id}: duplicate snapshot id {snapshot.id!r}"
            )
        existing.append(snapshot.to_dict())
        await self._store.async_save(data)
