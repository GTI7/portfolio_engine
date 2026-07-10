"""Cash-flow-excluded sub-period return series, shared by TwrCalculator and
VolatilityCalculator (Milestone 7). Extracted from TwrCalculator's own
internals because a second calculator now needs the exact same series -
same rule already applied for engine/external_cash_flows.py: a helper gets
factored out when a second consumer needs it, not preemptively.

This is a plain shared function, not calculator-to-calculator composition -
no calculator calls another calculator anywhere in this project.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .external_cash_flows import extract_external_cash_flows
from .models import Portfolio, Position

#: Same three-way-plus-ok status vocabulary as every other engine result
#: type (MwrResult, TwrResult, ReconciliationResult) - "not computable" is
#: a distinct claim from "computed and there's no return," and both are
#: distinct from "nothing to compute from at all."
STATUS_NO_DATA = "no_data"
STATUS_INSUFFICIENT_DATA = "insufficient_data"
STATUS_NOT_COMPUTABLE = "not_computable"
STATUS_OK = "ok"


@dataclass
class PeriodReturn:
    start: datetime
    end: datetime
    return_fraction: float  # e.g. 0.05 for +5%, NOT a percentage, NOT annualized


@dataclass
class PeriodReturnsResult:
    status: str
    periods: list[PeriodReturn] = field(default_factory=list)


def compute_period_returns(
    portfolio: Portfolio, positions: list[Position], as_of: datetime
) -> PeriodReturnsResult:
    """Link consecutive Snapshots (plus a synthetic final boundary at the
    current live portfolio value, if `as_of` is later than the last real
    Snapshot) into a series of cash-flow-excluded sub-period returns.

    See TwrCalculator's docstring for the full method description (the
    `(end_value - net_injection) / begin_value - 1` formula, the sign-
    convention note, and the documented approximation this implies given
    once-per-day snapshotting) - this function is exactly that logic,
    unchanged, just returning the period series instead of compounding it
    into a single cumulative figure.
    """
    snapshots = sorted(
        (s for s in portfolio.snapshots if s.timestamp <= as_of), key=lambda s: s.timestamp
    )
    if not snapshots:
        return PeriodReturnsResult(status=STATUS_NO_DATA)

    boundaries: list[tuple[datetime, float]] = [
        (s.timestamp, s.portfolio_value) for s in snapshots
    ]
    if as_of > snapshots[-1].timestamp:
        current_value = sum(p.market_value_base for p in positions) + portfolio.cash_balance
        boundaries.append((as_of, current_value))

    if len(boundaries) < 2:
        return PeriodReturnsResult(status=STATUS_INSUFFICIENT_DATA)

    flows = sorted(extract_external_cash_flows(portfolio.transactions), key=lambda f: f[0])

    # Single sorted-merge pass over periods and flows together -
    # O(periods + flows), not O(periods * flows) - see BENCHMARKS.md's
    # Milestone 6 entry for why this matters over long histories.
    flow_idx = 0
    first_t0 = boundaries[0][0]
    while flow_idx < len(flows) and flows[flow_idx][0] <= first_t0:
        flow_idx += 1

    periods: list[PeriodReturn] = []
    for (t0, v0), (t1, v1) in zip(boundaries, boundaries[1:], strict=False):
        if v0 <= 0:
            return PeriodReturnsResult(status=STATUS_NOT_COMPUTABLE, periods=periods)

        period_injection = 0.0
        while flow_idx < len(flows) and flows[flow_idx][0] <= t1:
            period_injection += -flows[flow_idx][1]
            flow_idx += 1

        periods.append(
            PeriodReturn(start=t0, end=t1, return_fraction=(v1 - period_injection) / v0 - 1)
        )

    return PeriodReturnsResult(status=STATUS_OK, periods=periods)
