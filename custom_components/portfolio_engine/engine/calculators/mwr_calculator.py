from __future__ import annotations

from datetime import UTC, datetime

from ..external_cash_flows import extract_external_cash_flows
from ..models import MwrResult, Portfolio, Position
from ..xirr import xirr
from .base import Calculator


class MwrCalculator(Calculator):
    """Money-weighted return (XIRR) - the annualized rate that makes the
    net present value of the portfolio's external cash flows (contributions
    negative, withdrawals/terminal value positive) equal zero.

    Cash-flow classification is engine/external_cash_flows.py (shared with
    TwrCalculator, Milestone 6) per
    docs/adr/0011-mwr-external-cash-flow-classification.md - this class no
    longer carries its own copy of that logic.

    `as_of` is constructor-injectable (defaulting to real "now" at call
    time) specifically so tests can supply a fixed datetime instead of
    depending on wall-clock time - same pattern as
    AllocationCalculator(group_by=...).
    """

    def __init__(self, as_of: datetime | None = None):
        self._as_of = as_of

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> MwrResult:
        as_of = self._as_of or datetime.now(UTC)

        external_flows = extract_external_cash_flows(portfolio.transactions)

        if not external_flows:
            return MwrResult(status="no_data", cash_flow_count=0, as_of=as_of)

        total_value = sum(p.market_value_base for p in positions) + portfolio.cash_balance
        cash_flows = [*external_flows, (as_of, total_value)]

        if len({date for date, _ in cash_flows}) < 2:
            # every flow (including the terminal one) landed on the same
            # date - no time spread for a rate to be meaningful over.
            return MwrResult(
                status="insufficient_data", cash_flow_count=len(cash_flows), as_of=as_of
            )

        has_negative = any(amount < 0 for _, amount in cash_flows)
        has_positive = any(amount > 0 for _, amount in cash_flows)
        if not (has_negative and has_positive):
            return MwrResult(
                status="insufficient_data", cash_flow_count=len(cash_flows), as_of=as_of
            )

        result = xirr(cash_flows)
        if result.rate is None:
            return MwrResult(
                status="not_computable", cash_flow_count=len(cash_flows), as_of=as_of
            )

        return MwrResult(
            status="ok",
            rate_pct=round(result.rate * 100, 4),
            cash_flow_count=len(cash_flows),
            as_of=as_of,
        )
