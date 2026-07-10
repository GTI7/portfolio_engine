"""Repository interface — retrieves and persists portfolio data ONLY.

Per user guidance: repositories never calculate portfolio metrics. A
repository returns raw `Holding`/`Portfolio` objects exactly as configured;
all math happens in engine/calculators. See ADR-0001.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from engine.models import Portfolio, Transaction


class PortfolioRepository(ABC):
    @abstractmethod
    async def async_get_portfolios(self) -> list[Portfolio]:
        """Return all portfolios with their configured holdings.

        Must NOT attach prices, values, or any derived figure — that's the
        engine's job once quotes are available. A repository that returns
        a `market_value` on anything is a bug.

        Per Milestone 4, implementations that support transactions should
        also populate `Portfolio.transactions` here (a single read, same
        as holdings) rather than requiring a caller to separately call
        `async_get_transactions` for every portfolio just to get a
        complete `Portfolio` object.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    # --- Transaction support (Milestone 4) ---------------------------------
    # Concrete, non-abstract, with safe defaults: adding these to the ABC
    # must not force any existing or hypothetical repository implementation
    # to change. A repository that doesn't override them simply doesn't
    # support transactions — `supports_transactions` says so, and
    # `async_get_transactions` returns an empty list rather than raising,
    # so callers that don't care can treat "unsupported" and "no
    # transactions yet" identically if they want to.

    @property
    def supports_transactions(self) -> bool:
        return False

    async def async_get_transactions(self, portfolio_id: str) -> list[Transaction]:
        return []
