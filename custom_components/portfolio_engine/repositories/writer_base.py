"""Portfolio write interface - creates and appends to portfolio data ONLY.

Deliberately separate from PortfolioRepository (repositories/base.py), never
merged into it - see docs/adr/0015-separate-portfolio-writer-interface.md.
Reading a portfolio and mutating its backing files are different questions,
per the same "different questions get different interfaces" precedent
ADR-0002 established for PriceProvider/CurrencyProvider and
MILESTONE_11_DESIGN.md reapplied for AssetSearchProvider. Keeping writes on
their own interface means PortfolioRepository's existing "no side effects"
contract - the one every caller (coordinator, every calculator,
export_portfolio_data) already depends on - never has to be re-audited.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..engine.models import Holding, Transaction


class PortfolioWriter(ABC):
    @abstractmethod
    async def async_create_portfolio(
        self,
        portfolio_id: str,
        name: str,
        base_currency: str,
        cash_balance: float,
        holdings: list[Holding],
    ) -> None:
        """Create a brand-new portfolio at `portfolio_id`. Must raise if a
        portfolio already exists at this id - creation is never an upsert
        (see docs/adr/0018-assisted-setup-splits-config-flow-and-service.md).
        """
        raise NotImplementedError

    @abstractmethod
    async def async_append_transactions(
        self, portfolio_id: str, transactions: list[Transaction]
    ) -> None:
        """Append new transactions to an existing portfolio's transaction
        log. Must never rewrite, reorder, or drop any transaction already
        present - append-only, matching the transaction log's own
        immutable, append-only convention (docs/adr/0010).
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
