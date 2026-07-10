"""Baseline performance benchmark for the Portfolio Engine.

Not a test (nothing here asserts pass/fail) and not an optimization
exercise — per the milestone guidance, the goal is a recorded baseline that
future milestones can be compared against, so a regression (or a genuine
improvement) is visible rather than assumed.

Usage:
    python scripts/benchmark.py [--sizes 100,500,1000] [--repeats 5]
                                 [--snapshot-days 100,500,1000,2000]

Writes a Markdown report to stdout; redirect to BENCHMARKS.md to update the
recorded baseline. Two independent dimensions are measured (Milestone 6):
holdings count (as before) and snapshot-history length — kept separate
because they stress different code paths, and conflating them into one
sweep would hide an O(n^2) regression in either one specifically.
"""
from __future__ import annotations

import argparse
import dataclasses
import statistics
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import __version__ as engine_version  # noqa: E402
from engine.calculators.allocation_calculator import AllocationCalculator  # noqa: E402
from engine.calculators.dividend_calculator import DividendCalculator  # noqa: E402
from engine.calculators.drawdown_calculator import DrawdownCalculator  # noqa: E402
from engine.calculators.mwr_calculator import MwrCalculator  # noqa: E402
from engine.calculators.performance_calculator import PerformanceCalculator  # noqa: E402
from engine.calculators.portfolio_calculator import PortfolioCalculator  # noqa: E402
from engine.calculators.position_analytics_calculator import (  # noqa: E402
    PositionAnalyticsCalculator,
)
from engine.calculators.reconciliation_calculator import ReconciliationCalculator  # noqa: E402
from engine.calculators.transaction_calculator import TransactionCalculator  # noqa: E402
from engine.calculators.twr_calculator import TwrCalculator  # noqa: E402
from engine.calculators.volatility_calculator import VolatilityCalculator  # noqa: E402
from engine.models import (  # noqa: E402
    Holding,
    Portfolio,
    Quote,
    Snapshot,
    Transaction,
    TransactionType,
)
from engine.portfolio_engine import PortfolioEngine  # noqa: E402

ASSET_TYPES = ["stock", "etf", "crypto", "fund"]
BASE_DATE = datetime.fromisoformat("2025-01-01T00:00:00+00:00")
# Comfortably covers the worst-case total cost basis at 1000 holdings
# (shares 10-59, avg_price 50-249 -> up to ~5.2M) with margin, so
# Portfolio.cash_balance (which must be non-negative) never goes negative
# regardless of `size`.
OPENING_DEPOSIT = 20_000_000.0
#: A small, fixed snapshot history attached to every holdings-scaling run,
#: so that table exercises TwrCalculator realistically without conflating
#: holdings-count scaling with snapshot-count scaling (that's the second,
#: separate benchmark below).
FIXED_SNAPSHOT_HISTORY_DAYS = 30


def build_snapshot_history(
    days: int, portfolio_value_start: float = 20_000_000.0
) -> list[Snapshot]:
    """A daily snapshot history of the given length, values drifting
    gently upward - realistic enough to exercise TwrCalculator's period
    linking without needing to match any particular portfolio's real state.
    """
    snapshots = []
    value = portfolio_value_start
    for day in range(days):
        value *= 1.0003  # a small, steady daily drift
        snapshots.append(
            Snapshot(
                id=str(uuid.uuid4()),
                portfolio_id="bench",
                timestamp=BASE_DATE + timedelta(days=day),
                portfolio_value=round(value, 2),
                cash_balance=0.0,
                invested=portfolio_value_start,
                base_currency="USD",
            )
        )
    return snapshots


def build_synthetic_portfolio(
    size: int, snapshot_days: int = FIXED_SNAPSHOT_HISTORY_DAYS
) -> tuple[Portfolio, dict[str, Quote]]:
    holdings = []
    quotes: dict[str, Quote] = {}
    transactions: list[Transaction] = [
        Transaction(
            id="opening-deposit",
            portfolio_id="bench",
            type=TransactionType.DEPOSIT,
            date=BASE_DATE,
            currency="USD",
            amount=OPENING_DEPOSIT,
        )
    ]
    for i in range(size):
        symbol = f"SYM{i:05d}"
        shares = 10 + (i % 50)
        avg_price = 50 + (i % 200)
        holdings.append(
            Holding(
                symbol=symbol,
                shares=shares,
                avg_price=avg_price,
                currency="USD",
                type=ASSET_TYPES[i % len(ASSET_TYPES)],
            )
        )
        quotes[symbol] = Quote(
            symbol=symbol,
            price=avg_price * (1 + ((i % 21) - 10) / 100),  # +/-10% synthetic move
            currency="USD",
            change_pct=(i % 21) - 10,
        )
        # One matching BUY per holding, so transaction_replay/reconciliation
        # (Milestone 4) has a realistic log to process at every portfolio
        # size, not an empty one that would understate their cost.
        transactions.append(
            Transaction(
                id=f"buy-{symbol}",
                portfolio_id="bench",
                type=TransactionType.BUY,
                date=BASE_DATE + timedelta(days=i % 365),
                currency="USD",
                amount=shares * avg_price,
                symbol=symbol,
                shares=shares,
                price=avg_price,
            )
        )
    portfolio = Portfolio(
        id="bench",
        name="Benchmark",
        holdings=holdings,
        base_currency="USD",
        cash_balance=OPENING_DEPOSIT - sum(h.shares * h.avg_price for h in holdings),
        transactions=transactions,
        snapshots=build_snapshot_history(snapshot_days) if snapshot_days else [],
    )
    return portfolio, quotes


def build_engine() -> PortfolioEngine:
    # All 11 calculators as of Milestone 7 — matches _build_engine() in
    # custom_components/portfolio_engine/coordinator.py, so this benchmark
    # reflects what a real coordinator tick actually costs, not a partial
    # subset that would understate it.
    return PortfolioEngine(
        {
            "summary": PortfolioCalculator(),
            "allocation": AllocationCalculator(group_by="type"),
            "performance": PerformanceCalculator(),
            "reconciliation": ReconciliationCalculator(),
            "transactions": TransactionCalculator(),
            "mwr": MwrCalculator(),
            "twr": TwrCalculator(),
            "dividends": DividendCalculator(),
            "drawdown": DrawdownCalculator(),
            "volatility": VolatilityCalculator(),
            "concentration": PositionAnalyticsCalculator(),
        }
    )


def _time_engine_run(
    portfolio: Portfolio, quotes: dict[str, Quote], repeats: int
) -> dict[str, float]:
    engine = build_engine()
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        engine.run(portfolio, quotes)
        timings.append((time.perf_counter() - start) * 1000)  # ms
    return {
        "mean_ms": statistics.mean(timings),
        "median_ms": statistics.median(timings),
        "max_ms": max(timings),
        "min_ms": min(timings),
    }


def benchmark_holdings_size(size: int, repeats: int) -> dict[str, float]:
    portfolio, quotes = build_synthetic_portfolio(size)
    result = _time_engine_run(portfolio, quotes, repeats)
    result["size"] = size
    return result


def benchmark_snapshot_history(days: int, repeats: int, holdings: int = 20) -> dict[str, float]:
    """Fixed, modest holdings count; snapshot history length is the only
    thing varying - isolates TwrCalculator/snapshot-lookup cost from
    holdings-count cost, per Milestone 6 Phase 6's explicit ask to watch
    for O(n^2) specifically "over long histories." A monthly deposit is
    added across the whole history (not just the single opening deposit
    the holdings-count benchmark uses) specifically to stress
    TwrCalculator's period/flow merge - this is exactly the "long history
    AND many external flows" combination that would have been O(n*m)
    before this milestone's merge-pass fix (see BENCHMARKS.md).
    """
    portfolio, quotes = build_synthetic_portfolio(holdings, snapshot_days=days)
    monthly_deposits = [
        Transaction(
            id=f"monthly-deposit-{i}",
            portfolio_id="bench",
            type=TransactionType.DEPOSIT,
            date=BASE_DATE + timedelta(days=i * 30),
            currency="USD",
            amount=1000.0,
        )
        for i in range(days // 30 + 1)
    ]
    portfolio = dataclasses.replace(
        portfolio, transactions=[*portfolio.transactions, *monthly_deposits]
    )
    result = _time_engine_run(portfolio, quotes, repeats)
    result["days"] = days
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="100,500,1000")
    parser.add_argument("--snapshot-days", default="100,500,1000,2000")
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    sizes = [int(s) for s in args.sizes.split(",")]
    snapshot_days = [int(d) for d in args.snapshot_days.split(",")]

    print(f"# Portfolio Engine Benchmark — engine v{engine_version}\n")
    print(f"Python {sys.version.split()[0]} · {args.repeats} repeats per size, "
          f"full `PortfolioEngine.run()` (11 calculators: summary, allocation, "
          f"performance, reconciliation, transactions, mwr, twr, dividends, "
          f"drawdown, volatility, concentration)\n")

    print(f"## By holdings count (fixed {FIXED_SNAPSHOT_HISTORY_DAYS}-day snapshot "
          f"history, 1 transaction per holding)\n")
    print("| Holdings | Mean (ms) | Median (ms) | Min (ms) | Max (ms) |")
    print("|---|---|---|---|---|")
    for size in sizes:
        result = benchmark_holdings_size(size, args.repeats)
        print(
            f"| {result['size']} | {result['mean_ms']:.3f} | {result['median_ms']:.3f} | "
            f"{result['min_ms']:.3f} | {result['max_ms']:.3f} |"
        )

    print("\n## By snapshot history length (fixed 20 holdings) — "
          "watching for O(n^2) over long histories\n")
    print("| Snapshot Days | Mean (ms) | Median (ms) | Min (ms) | Max (ms) |")
    print("|---|---|---|---|---|")
    for days in snapshot_days:
        result = benchmark_snapshot_history(days, args.repeats)
        print(
            f"| {result['days']} | {result['mean_ms']:.3f} | {result['median_ms']:.3f} | "
            f"{result['min_ms']:.3f} | {result['max_ms']:.3f} |"
        )


if __name__ == "__main__":
    main()
