from __future__ import annotations

import statistics
from datetime import UTC, datetime

from ..models import Portfolio, Position, VolatilityResult
from ..period_returns import STATUS_OK, compute_period_returns
from .base import Calculator

#: Minimum periods needed for a meaningful standard deviation - stdev of
#: a single value is trivially 0 and not a real measurement.
MIN_PERIODS = 2


class VolatilityCalculator(Calculator):
    """Standard deviation of period returns, annualized - a standard risk
    metric, independent of and complementary to the return metrics
    (ROI/MWR/TWR).

    Uses the SAME cash-flow-excluded sub-period return series
    engine/period_returns.py provides to TwrCalculator - this is not
    optional: using raw, flow-polluted returns would make volatility
    partly measure deposit/withdrawal timing instead of market risk, a
    correctness bug, not a style choice (see
    MILESTONE_7_DESIGN.md's "one real helper extraction" section).

    Annualization uses the average observed period length to derive a
    periods-per-year scaling factor
    (`sqrt(365 / average_period_length_days)`), since snapshots are not
    guaranteed to be exactly daily (gaps are allowed, per Milestone 6).
    """

    def __init__(self, as_of: datetime | None = None):
        self._as_of = as_of

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> VolatilityResult:
        as_of = self._as_of or datetime.now(UTC)

        result = compute_period_returns(portfolio, positions, as_of)
        if result.status != STATUS_OK or len(result.periods) < MIN_PERIODS:
            status = result.status if result.status != STATUS_OK else "insufficient_data"
            return VolatilityResult(
                status=status, sample_count=len(result.periods), as_of=as_of
            )

        returns = [p.return_fraction for p in result.periods]
        period_stdev = statistics.stdev(returns)

        total_days = (result.periods[-1].end - result.periods[0].start).days
        average_period_days = total_days / len(result.periods) if result.periods else 0
        periods_per_year = (365 / average_period_days) if average_period_days > 0 else 0
        annualized_stdev = period_stdev * (periods_per_year**0.5)

        return VolatilityResult(
            status="ok",
            daily_volatility_pct=round(period_stdev * 100, 4),
            annualized_volatility_pct=round(annualized_stdev * 100, 4),
            observation_period_days=total_days,
            sample_count=len(result.periods),
            as_of=as_of,
        )
