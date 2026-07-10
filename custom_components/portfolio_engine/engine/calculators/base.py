"""Calculator plugin interface.

Per ADR-0004, only three calculators exist yet (PortfolioCalculator,
AllocationCalculator, PerformanceCalculator). Per ADR-0005, calculators are
called unconditionally on every engine run — the `triggers` concept from the
event-driven design is documented in the architecture doc but not
implemented here; adding it later does not require changing this base class.

Signature takes the full `Portfolio`, not just `base_currency`, so that
calculators can see portfolio-level data — cash_balance being the first
example (ADR-0008). Positions are still passed separately since they're
already-assembled engine output, not raw config.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import Portfolio, Position


class Calculator(ABC):
    """A pure function over portfolio state. No I/O, no HA imports."""

    @abstractmethod
    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> Any:
        """Compute this calculator's result from the current positions.

        `positions` already have market value / cost basis / gain populated
        by the time any calculator runs (that assembly step lives in
        PortfolioEngine, not in individual calculators) — calculators only
        aggregate or derive from that, they don't repeat position-level math.
        """
        raise NotImplementedError
