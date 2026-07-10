"""SnapshotRepository interface — retrieves and persists Snapshots ONLY.

Separate from PortfolioRepository per ADR-0012: snapshots are self-generated
operational data, not user/external-declared config or events, and their
production storage (Home Assistant's Store helper) is HA-specific in a way
holdings/transactions' YAML storage isn't.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from engine.models import Snapshot


class SnapshotRepository(ABC):
    @abstractmethod
    async def async_get_snapshots(self, portfolio_id: str) -> list[Snapshot]:
        """Return all snapshots for a portfolio, in chronological order."""
        raise NotImplementedError

    @abstractmethod
    async def async_append_snapshot(self, snapshot: Snapshot) -> None:
        """Persist one new snapshot. Append-only - snapshots are immutable
        once written (same convention as Transaction, Milestone 4); there
        is deliberately no update/delete method on this interface.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
