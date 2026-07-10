"""Snapshot collection policy - pure functions, HA-independent, matching
transaction_replay.py/xirr.py's separation pattern. The coordinator (HA
layer) is responsible for *calling* these after a successful refresh and
persisting the result via SnapshotRepository; this module only decides
*whether* a snapshot should be created and *how* to build one from current
engine output - it has no knowledge of scheduling, HA, or storage.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from .models import HoldingSnapshot, Portfolio, PortfolioSummary, Position, Snapshot


def should_create_snapshot(existing_snapshots: list[Snapshot], now: datetime) -> bool:
    """Policy: at most one snapshot per calendar date (`now`'s date, in
    whatever timezone `now` carries - the coordinator is responsible for
    passing a consistent one, typically UTC). Deliberately date-based, not
    exact-timestamp-based - "once per day" (MILESTONE_6's own stated
    policy) means comparing dates, not requiring two calls at the exact
    same microsecond to count as a duplicate.
    """
    today = now.date()
    return not any(s.timestamp.date() == today for s in existing_snapshots)


def build_snapshot(
    portfolio: Portfolio,
    summary: PortfolioSummary,
    positions: list[Position],
    timestamp: datetime,
) -> Snapshot:
    """Build a Snapshot from the engine's current output for this
    portfolio. `summary`/`positions` are exactly what PortfolioCalculator/
    PortfolioEngine.build_positions already produce each run - this
    function doesn't compute anything new, it just packages an existing
    result into the immutable historical record.
    """
    holdings = [
        HoldingSnapshot(
            symbol=p.symbol,
            shares=p.holding.shares,
            market_value_base=p.market_value_base,
        )
        for p in positions
    ]
    return Snapshot(
        id=str(uuid.uuid4()),
        portfolio_id=portfolio.id,
        timestamp=timestamp,
        portfolio_value=summary.total_value,
        cash_balance=summary.cash_balance,
        invested=summary.total_invested,
        base_currency=portfolio.base_currency,
        holdings=holdings,
    )
