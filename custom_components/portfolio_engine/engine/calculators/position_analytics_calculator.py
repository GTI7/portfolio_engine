from __future__ import annotations

from ..models import Portfolio, Position, PositionAnalyticsResult, PositionSummary
from .base import Calculator

TOP_N = 5


class PositionAnalyticsCalculator(Calculator):
    """Concentration and per-position standouts, purely derived from
    `positions` (already available every run - no snapshot/transaction
    dependency, the simplest of Milestone 7's four new calculators).

    One entity (`sensor.<portfolio>_concentration`), rich attributes -
    largest position %, largest winner/loser, top-5 concentration,
    diversification score, and the Herfindahl-Hirschman Index are all
    attributes on the same result, not separate entities.

    `diversification_score` and `herfindahl_index` are both derived from
    the same underlying weight distribution (HHI = sum of squared
    portfolio-share fractions; `diversification_score` is `(1 - HHI) *
    100`, rescaled so 0 means "fully concentrated in one position" and 100
    means "perfectly even across every position" - the same information
    as HHI, just in a direction most people read as "bigger is better,"
    which raw HHI is not (HHI is smaller for more diversified portfolios).
    Both are exposed since neither fully subsumes the other's readability
    for different audiences.
    """

    def calculate(
        self, portfolio: Portfolio, positions: list[Position]
    ) -> PositionAnalyticsResult:
        if not positions:
            return PositionAnalyticsResult(status="no_data", holding_count=0)

        total_value = sum(p.market_value_base for p in positions)
        if total_value <= 0:
            return PositionAnalyticsResult(status="no_data", holding_count=len(positions))

        summaries = sorted(
            (
                PositionSummary(
                    symbol=p.symbol,
                    pct_of_portfolio=round(p.market_value_base / total_value * 100, 4),
                    gain_pct=p.gain_pct,
                )
                for p in positions
            ),
            key=lambda s: s.pct_of_portfolio,
            reverse=True,
        )

        largest_position = summaries[0]
        largest_winner = max(summaries, key=lambda s: s.gain_pct)
        largest_loser = min(summaries, key=lambda s: s.gain_pct)

        top5_concentration_pct = round(sum(s.pct_of_portfolio for s in summaries[:TOP_N]), 4)

        weights = [p.market_value_base / total_value for p in positions]
        herfindahl_index = round(sum(w**2 for w in weights), 6)
        diversification_score = round((1 - herfindahl_index) * 100, 2)

        return PositionAnalyticsResult(
            status="ok",
            largest_position=largest_position,
            largest_winner=largest_winner,
            largest_loser=largest_loser,
            top5_concentration_pct=top5_concentration_pct,
            diversification_score=diversification_score,
            herfindahl_index=herfindahl_index,
            holding_count=len(positions),
        )
