"""Market data provider interface — supplies quotes ONLY.

Per ADR-0002, this is deliberately separate from PortfolioRepository.
Currency conversion is out of scope for this interface too (see the
architecture doc's Section 3, CurrencyProvider) — deferred to Milestone 3,
not implemented in Milestone 1.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..engine.models import Quote


class PriceProvider(ABC):
    @abstractmethod
    async def async_get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Return a symbol -> Quote map. Should batch internally where the
        underlying API supports it (see YahooFinanceProvider for why this
        matters at scale).
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
