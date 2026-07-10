from __future__ import annotations

from collections import defaultdict

from ..models import AllocationGroup, Portfolio, Position
from .base import Calculator

CASH_LABEL = "Cash"


class AllocationCalculator(Calculator):
    """Groups positions by an arbitrary attribute (asset type, currency, ...).

    Cash is included as its own group (ADR-0008) whenever
    `portfolio.cash_balance > 0`, computed against total value (positions +
    cash) so percentages across all groups sum to 100 including cash - a
    portfolio that's 20% cash should show 20% cash, not have cash silently
    excluded from the denominator.

    Sector/region grouping will work the same way once those fields exist
    on Holding (deferred - see architecture doc Section 7 on the domain
    model, and ADR-0004 on not pre-building unused fields).
    """

    def __init__(self, group_by: str = "type"):
        self._group_by = group_by

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> list[AllocationGroup]:
        total = sum(p.market_value_base for p in positions) + portfolio.cash_balance
        groups: dict[str, float] = defaultdict(float)
        for p in positions:
            key = getattr(p.holding, self._group_by, None) or "Unclassified"
            groups[key] += p.market_value_base

        if portfolio.cash_balance > 0:
            groups[CASH_LABEL] += portfolio.cash_balance

        if total == 0:
            return [AllocationGroup(label=k, value=round(v, 2), pct=0.0) for k, v in groups.items()]

        return sorted(
            (
                AllocationGroup(label=k, value=round(v, 2), pct=round(v / total * 100, 1))
                for k, v in groups.items()
            ),
            key=lambda g: -g.value,
        )
