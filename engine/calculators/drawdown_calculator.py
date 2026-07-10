from __future__ import annotations

from datetime import UTC, datetime

from ..models import DrawdownResult, Portfolio, Position
from .base import Calculator

#: Below this, a drawdown is treated as "at peak" rather than a fractional
#: sliver of negative percentage from floating-point noise - same spirit
#: as ReconciliationCalculator's TOLERANCE constant.
AT_PEAK_TOLERANCE_PCT = 0.01


class DrawdownCalculator(Calculator):
    """Current and maximum drawdown - how far below the portfolio's
    running peak value it is right now, and how far it ever fell,
    computed from `portfolio.snapshots` plus the same synthetic
    "current value at `as_of`" convention TwrCalculator/MwrCalculator use.

    Unlike TwrCalculator/VolatilityCalculator, this does NOT use
    engine/period_returns.py's cash-flow-excluded return series -
    drawdown is a statement about the portfolio's actual value trajectory
    (would a real investor watching their balance have seen it fall this
    far), which is exactly what deposits/withdrawals SHOULD be allowed to
    move, not something to exclude. A withdrawal that visibly drops the
    balance is a real drop in what's sitting in the account, even though
    it isn't investment underperformance - TWR/MWR/Volatility care about
    performance; Drawdown cares about the raw value line.
    """

    def __init__(self, as_of: datetime | None = None):
        self._as_of = as_of

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> DrawdownResult:
        as_of = self._as_of or datetime.now(UTC)

        snapshots = sorted(
            (s for s in portfolio.snapshots if s.timestamp <= as_of), key=lambda s: s.timestamp
        )
        if not snapshots:
            return DrawdownResult(status="no_data", as_of=as_of)

        points: list[tuple[datetime, float]] = [
            (s.timestamp, s.portfolio_value) for s in snapshots
        ]
        if as_of > snapshots[-1].timestamp:
            current_value = sum(p.market_value_base for p in positions) + portfolio.cash_balance
            points.append((as_of, current_value))

        peak_value = points[0][1]
        peak_date = points[0][0]
        max_drawdown_pct = 0.0

        for point_date, value in points:
            if value > peak_value:
                peak_value = value
                peak_date = point_date
            if peak_value > 0:
                drawdown_pct = (value - peak_value) / peak_value * 100
                max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)

        current_value = points[-1][1]
        current_drawdown_pct = (
            round((current_value - peak_value) / peak_value * 100, 4) if peak_value > 0 else 0.0
        )

        if current_drawdown_pct >= -AT_PEAK_TOLERANCE_PCT:
            recovery_status = "at_peak"
        elif current_drawdown_pct > max_drawdown_pct:
            recovery_status = "recovering"
        else:
            recovery_status = "in_drawdown"

        return DrawdownResult(
            status="ok",
            current_drawdown_pct=current_drawdown_pct,
            maximum_drawdown_pct=round(max_drawdown_pct, 4),
            peak_value=round(peak_value, 2),
            peak_date=peak_date,
            recovery_status=recovery_status,
            as_of=as_of,
        )
