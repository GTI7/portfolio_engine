from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..models import DividendResult, Portfolio, Position, TransactionType
from .base import Calculator


class DividendCalculator(Calculator):
    """Dividend income summary: rolling 12-month, current calendar year,
    lifetime, dividend yield (on cost), and average monthly dividend - all
    derived entirely from existing `DIVIDEND` transactions (Milestone 4),
    no new transaction type. One entity, rich attributes, per
    MILESTONE_7_DESIGN.md's explicit scope decision - not four separate
    entities for lifetime/yearly/yield.

    `as_of` is constructor-injectable, same pattern as every other
    time-sensitive calculator since Milestone 5 (MwrCalculator).
    """

    def __init__(self, as_of: datetime | None = None):
        self._as_of = as_of

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> DividendResult:
        as_of = self._as_of or datetime.now(UTC)

        # Filtered to <= as_of up front, once, so every figure below (not
        # just rolling/current-year) consistently ignores a dividend dated
        # in the future relative to as_of - a transaction log with a
        # forward-dated entry (e.g. an already-declared but not yet paid
        # dividend) shouldn't count anywhere until its date arrives.
        dividends = [
            t
            for t in portfolio.transactions
            if t.type == TransactionType.DIVIDEND and t.date <= as_of
        ]
        if not dividends:
            return DividendResult(status="no_data", as_of=as_of)

        lifetime = sum(t.amount for t in dividends)

        rolling_start = as_of - timedelta(days=365)
        rolling_12_months = sum(t.amount for t in dividends if t.date > rolling_start)

        current_year = sum(t.amount for t in dividends if t.date.year == as_of.year)

        first_dividend_date = min(t.date for t in dividends)
        months_observed = max(1.0, (as_of - first_dividend_date).days / 30.44)
        average_monthly_dividend = round(lifetime / months_observed, 2)

        total_invested = sum(p.cost_basis_base for p in positions)
        dividend_yield_pct = (
            round(rolling_12_months / total_invested * 100, 4) if total_invested > 0 else None
        )

        return DividendResult(
            status="ok",
            rolling_12_months=round(rolling_12_months, 2),
            current_year=round(current_year, 2),
            lifetime=round(lifetime, 2),
            dividend_yield_pct=dividend_yield_pct,
            average_monthly_dividend=average_monthly_dividend,
            as_of=as_of,
        )
