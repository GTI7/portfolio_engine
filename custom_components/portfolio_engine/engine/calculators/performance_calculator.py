from __future__ import annotations

from ..models import PerformanceResult, Portfolio, Position
from .base import Calculator


class PerformanceCalculator(Calculator):
    """Day-over-day change today; weekly/monthly/YTD are stubbed at 0.0
    until the history layer (Milestone 7, ADR-0003) exists to compute them
    from. See PerformanceResult's docstring for why they're explicit fields
    rather than omitted.

    Cash is included in the weighting denominator (ADR-0008) - it
    contributes 0% change itself, which correctly dilutes the portfolio's
    overall day-change the same way it would in reality (uninvested cash
    doesn't move with the market).
    """

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> PerformanceResult:
        total_value = sum(p.market_value_base for p in positions) + portfolio.cash_balance
        if total_value == 0:
            return PerformanceResult(day_change_pct=0.0)

        weighted_change = sum(
            p.day_change_pct * (p.market_value_base / total_value) for p in positions
        )
        # cash's implicit contribution is 0.0 * (cash_balance / total_value) - omitted
        # rather than written out, since it's always a no-op term.
        return PerformanceResult(day_change_pct=round(weighted_change, 2))
