from __future__ import annotations

from datetime import UTC, datetime

from ..models import Portfolio, Position, TwrResult
from ..period_returns import STATUS_OK, compute_period_returns
from .base import Calculator


class TwrCalculator(Calculator):
    """Time-weighted return - the compounded return an investor would have
    earned holding this portfolio, with the timing/size of deposits and
    withdrawals factored OUT (unlike MwrCalculator's XIRR, which is
    deliberately sensitive to them).

    The sub-period return series itself (linking consecutive Snapshots,
    excluding external cash flows per engine/external_cash_flows.py's
    classification) is computed by the shared engine/period_returns.py
    helper (Milestone 7 - extracted once VolatilityCalculator needed the
    same series; see that module's docstring). This class's own job is
    just compounding those sub-period returns into one cumulative figure,
    and - Milestone 7 - annualizing it into `annualized_pct` (CAGR),
    exactly the field Milestone 6 deferred rather than baking into
    `twr_pct` itself.

    `twr_pct` remains CUMULATIVE (holding-period), not annualized - see
    TwrResult's docstring. `annualized_pct` is the same return expressed
    as a compound annual rate over the elapsed period (first period's
    start to `as_of`) - standard CAGR conversion,
    `(1 + twr_pct/100) ** (365 / elapsed_days) - 1`, `None` whenever
    `twr_pct` itself is `None` or the elapsed period is zero days.
    """

    def __init__(self, as_of: datetime | None = None):
        self._as_of = as_of

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> TwrResult:
        as_of = self._as_of or datetime.now(UTC)

        result = compute_period_returns(portfolio, positions, as_of)
        if result.status != STATUS_OK:
            return TwrResult(status=result.status, periods_used=len(result.periods), as_of=as_of)

        cumulative = 1.0
        for period in result.periods:
            cumulative *= 1 + period.return_fraction
        twr_pct = round((cumulative - 1) * 100, 4)

        elapsed_days = (result.periods[-1].end - result.periods[0].start).days
        annualized_pct = (
            round((cumulative ** (365 / elapsed_days) - 1) * 100, 4) if elapsed_days > 0 else None
        )

        return TwrResult(
            status="ok",
            twr_pct=twr_pct,
            annualized_pct=annualized_pct,
            periods_used=len(result.periods),
            as_of=as_of,
        )
