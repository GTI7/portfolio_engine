"""Sanity check that the benchmark harness itself works, not a performance
assertion — CI shouldn't fail because a shared runner is slow today. Actual
baseline tracking is manual: re-run scripts/benchmark.py and compare against
BENCHMARKS.md when something might affect engine performance.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from benchmark import (  # noqa: E402
    benchmark_holdings_size,
    benchmark_snapshot_history,
    build_synthetic_portfolio,
)


def test_synthetic_portfolio_builds_requested_size():
    portfolio, quotes = build_synthetic_portfolio(50)
    assert len(portfolio.holdings) == 50
    assert len(quotes) == 50


def test_benchmark_holdings_runs_and_returns_timings():
    result = benchmark_holdings_size(size=20, repeats=2)
    assert result["size"] == 20
    assert result["mean_ms"] > 0
    assert result["min_ms"] <= result["mean_ms"] <= result["max_ms"]


def test_benchmark_snapshot_history_runs_and_returns_timings():
    result = benchmark_snapshot_history(days=10, repeats=2)
    assert result["days"] == 10
    assert result["mean_ms"] > 0
    assert result["min_ms"] <= result["mean_ms"] <= result["max_ms"]
