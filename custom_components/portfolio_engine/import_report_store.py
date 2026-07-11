"""Store-backed persistence for the most recent ImportReport per portfolio.

Deliberately NOT a new generic repository interface (unlike
SnapshotRepository, ADR-0012) - this only ever stores one thing (the last
report) per portfolio, not an open-ended, growing collection with
load/append semantics multiple implementations might need. A direct
`homeassistant.helpers.storage.Store` wrapper is the right amount of
abstraction for a single-blob need; inventing a new "Repository" pattern
instance for it would be exactly the kind of unnecessary architecture
MILESTONE_9's own guiding principle warns against ("can this be
implemented by plugging into the existing platform instead of extending
it" - here, "existing platform" already includes Store itself, no
interface layer needed on top).
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .importers.report import ImportReport

STORAGE_VERSION = 1


class ImportReportStore:
    """One Store file per config entry, holding the most recent
    ImportReport per portfolio_id that entry has ever imported into.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str):
        self._store: Store[dict[str, dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, f"portfolio_engine_last_import_{entry_id}"
        )

    async def async_get_last_report(self, portfolio_id: str) -> ImportReport | None:
        data = await self._store.async_load() or {}
        raw = data.get(portfolio_id)
        return ImportReport.from_dict(raw) if raw else None

    async def async_save_report(self, report: ImportReport) -> None:
        data = await self._store.async_load() or {}
        data[report.portfolio_id] = report.to_dict()
        await self._store.async_save(data)

    async def async_clear_report(self, portfolio_id: str) -> None:
        """Milestone 12: called by apply_import once a report's `imported`
        rows have been written to transactions.yaml. Turns "pending" into
        "absent" rather than adding an `applied: bool` field - this store
        already only ever holds one thing, the *pending* report, per this
        class's own docstring; modeling "already applied" as "no longer
        present" keeps that scope intact instead of growing it. See
        docs/adr/0017.
        """
        data = await self._store.async_load() or {}
        data.pop(portfolio_id, None)
        await self._store.async_save(data)
