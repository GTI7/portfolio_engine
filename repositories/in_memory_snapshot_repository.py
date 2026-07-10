"""In-memory SnapshotRepository - the engine-level reference implementation
used by the standalone test suite (tests/) to exercise the interface's
ordering/duplicate-ID/migration-safety behavior without any Home Assistant
dependency. The production implementation (StoreSnapshotRepository) lives
only in custom_components/portfolio_engine/ - see ADR-0012.

Not intended as a real persistence mechanism (data is lost on process
exit) - purely a test double that implements the real interface honestly,
rather than a mock that only pretends to.
"""
from __future__ import annotations

from engine.models import Snapshot

from .snapshot_base import SnapshotRepository


class InMemorySnapshotRepository(SnapshotRepository):
    name = "in_memory"

    def __init__(self) -> None:
        self._snapshots: dict[str, list[Snapshot]] = {}

    async def async_get_snapshots(self, portfolio_id: str) -> list[Snapshot]:
        snapshots = self._snapshots.get(portfolio_id, [])
        # Chronological order, id as a stable tiebreak for equal
        # timestamps - same convention as YamlRepository's transaction
        # sort (date is the real ordering key, id never is on its own,
        # but a deterministic secondary key avoids order flapping between
        # calls when two snapshots share a timestamp).
        return sorted(snapshots, key=lambda s: (s.timestamp, s.id))

    async def async_append_snapshot(self, snapshot: Snapshot) -> None:
        existing = self._snapshots.setdefault(snapshot.portfolio_id, [])
        if any(s.id == snapshot.id for s in existing):
            raise ValueError(
                f"{snapshot.portfolio_id}: duplicate snapshot id {snapshot.id!r}"
            )
        existing.append(snapshot)
