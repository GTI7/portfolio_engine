"""Portfolio Engine orchestrator.

Single responsibility (per user guidance): transform portfolio data into
portfolio insights. It does NOT know about Home Assistant, dashboards,
notifications, or presentation - those are the coordinator's / sensor
platform's job, one layer up, outside this package.
"""
from __future__ import annotations

from typing import Any

from .calculators.base import Calculator
from .models import Portfolio, Position, Quote


class PortfolioEngine:
    def __init__(self, calculators: dict[str, Calculator]):
        """`calculators` is a name -> Calculator map so callers (and tests)
        can address individual results by name, e.g. results["allocation"].
        """
        self._calculators = calculators

    def build_positions(
        self,
        portfolio: Portfolio,
        quotes: dict[str, Quote],
        fx_rates: dict[str, float] | None = None,
    ) -> list[Position]:
        """Combine each Holding with its Quote into a Position with computed
        market value / cost basis / gain, converted to the portfolio's base
        currency. This assembly step is intentionally centralized here (not
        duplicated in every calculator) - see Calculator.calculate's
        docstring.

        `fx_rates` maps a holding's currency -> the rate that converts one
        unit of that currency into one unit of `portfolio.base_currency`
        (i.e. `amount_in_base = amount_in_currency * fx_rates[currency]`) -
        see providers/currency_base.py. A currency missing from `fx_rates`
        (including when `fx_rates` is omitted entirely) falls back to a rate
        of 1.0 - correct and lossless when that currency already equals the
        base currency, and a documented best-effort approximation otherwise
        (the caller - update_logic.py - surfaces missing rates so this isn't
        a silent inaccuracy; see its `fx_rates_missing` field).
        """
        rates = fx_rates or {}
        positions = []
        for holding in portfolio.holdings:
            quote = quotes.get(holding.symbol)
            price = quote.price if quote else 0.0
            market_value = price * holding.shares
            cost_basis = holding.avg_price * holding.shares

            if holding.currency == portfolio.base_currency:
                fx_rate = 1.0
            else:
                fx_rate = rates.get(holding.currency, 1.0)

            market_value_base = market_value * fx_rate
            cost_basis_base = cost_basis * fx_rate
            gain = market_value_base - cost_basis_base
            gain_pct = (gain / cost_basis_base * 100) if cost_basis_base else 0.0

            positions.append(
                Position(
                    holding=holding,
                    quote=quote,
                    market_value=round(market_value, 2),
                    market_value_base=round(market_value_base, 2),
                    cost_basis=round(cost_basis, 2),
                    cost_basis_base=round(cost_basis_base, 2),
                    unrealized_gain=round(gain, 2),
                    gain_pct=round(gain_pct, 2),
                    day_change_pct=round(quote.change_pct, 2) if quote else 0.0,
                    fx_rate=fx_rate,
                )
            )
        return positions

    def run(
        self,
        portfolio: Portfolio,
        quotes: dict[str, Quote],
        fx_rates: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Compute every registered calculator's result for this portfolio."""
        positions = self.build_positions(portfolio, quotes, fx_rates)
        return {
            "positions": positions,
            **{
                name: calc.calculate(portfolio, positions)
                for name, calc in self._calculators.items()
            },
        }
