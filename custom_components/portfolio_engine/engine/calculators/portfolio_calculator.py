from __future__ import annotations

from ..models import Portfolio, PortfolioSummary, Position
from .base import Calculator


class PortfolioCalculator(Calculator):
    """Headline portfolio-level figures: total value, invested, gain, ROI.

    All currency conversion happens once, centrally, in
    PortfolioEngine.build_positions (Milestone 3) - every Position already
    carries correct base-currency figures (market_value_base,
    cost_basis_base) by the time this calculator runs, so this class is
    pure aggregation with no FX logic of its own. This is exactly the
    "calculators don't repeat position-level math" rule from
    Calculator.calculate's docstring.

    Cash is folded in as a first-class contributor to total value (not a
    bolt-on) per ADR-0008 - `total_value = total_positions_value +
    cash_balance` (cash_balance is already stored in base currency on
    Portfolio, so no conversion is needed for it either), while `roi_pct`
    is deliberately computed against invested capital only, since
    uninvested cash has no gain/loss to report.
    """

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> PortfolioSummary:
        total_positions_value = sum(p.market_value_base for p in positions)
        total_invested = sum(p.cost_basis_base for p in positions)
        total_gain = total_positions_value - total_invested
        roi_pct = (total_gain / total_invested * 100) if total_invested else 0.0

        return PortfolioSummary(
            total_positions_value=round(total_positions_value, 2),
            cash_balance=round(portfolio.cash_balance, 2),
            total_value=round(total_positions_value + portfolio.cash_balance, 2),
            total_invested=round(total_invested, 2),
            total_unrealized_gain=round(total_gain, 2),
            roi_pct=round(roi_pct, 2),
        )
