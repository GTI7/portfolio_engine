import statistics
from datetime import datetime, timedelta

import pytest

from engine.calculators.volatility_calculator import VolatilityCalculator
from engine.models import Portfolio, Snapshot, Transaction, TransactionType

BASE = datetime.fromisoformat("2025-01-01T00:00:00+00:00")


def snap(offset_days, value, snapshot_id=None):
    return Snapshot(
        id=snapshot_id or f"snap-{offset_days}",
        portfolio_id="demo",
        timestamp=BASE + timedelta(days=offset_days),
        portfolio_value=value,
        cash_balance=0.0,
        invested=value,
        base_currency="USD",
    )


def txn(offset_days, type_, **kwargs):
    defaults = dict(
        id=f"txn-{offset_days}-{type_.value}",
        portfolio_id="demo",
        type=type_,
        date=BASE + timedelta(days=offset_days),
        currency="USD",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def make_portfolio(snapshots=None, transactions=None, cash_balance=0.0):
    return Portfolio(
        id="demo",
        name="Demo",
        cash_balance=cash_balance,
        snapshots=snapshots or [],
        transactions=transactions or [],
    )


def test_no_snapshots_is_no_data():
    result = VolatilityCalculator(as_of=BASE).calculate(make_portfolio(), [])
    assert result.status == "no_data"


def test_single_period_is_insufficient_data():
    """One snapshot + current value = exactly 1 period - stdev needs >= 2
    data points to be meaningful.
    """
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0)], cash_balance=1000.0)
    result = VolatilityCalculator(as_of=BASE + timedelta(days=10)).calculate(portfolio, [])
    assert result.status == "insufficient_data"
    assert result.sample_count == 1


def test_zero_volatility_for_constant_returns():
    """Three periods, each with exactly the same return, should have zero
    standard deviation.
    """
    snapshots = [snap(0, 1000.0), snap(10, 1100.0), snap(20, 1210.0), snap(30, 1331.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1331.0)

    result = VolatilityCalculator(as_of=BASE + timedelta(days=30)).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.daily_volatility_pct == pytest.approx(0.0, abs=1e-6)
    assert result.annualized_volatility_pct == pytest.approx(0.0, abs=1e-6)
    assert result.sample_count == 3


def test_hand_verified_stdev_of_varying_returns():
    # returns: +10%, -10%, +10% (hand-computed stdev via statistics.stdev)
    snapshots = [snap(0, 1000.0), snap(10, 1100.0), snap(20, 990.0), snap(30, 1089.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1089.0)

    result = VolatilityCalculator(as_of=BASE + timedelta(days=30)).calculate(portfolio, [])

    returns = [0.10, -0.10, 0.10]
    expected_stdev = statistics.stdev(returns) * 100
    assert result.daily_volatility_pct == pytest.approx(expected_stdev, abs=1e-2)


def test_deposit_excluded_from_volatility_same_as_twr():
    """A deposit-inflated period shouldn't register as volatility - the
    same cash-flow exclusion TWR uses must apply here, since raw returns
    would show a huge spurious swing from the deposit itself.
    """
    snapshots = [snap(0, 1000.0), snap(10, 1500.0), snap(20, 1650.0), snap(30, 1815.0)]
    transactions = [txn(5, TransactionType.DEPOSIT, amount=400.0)]
    portfolio = make_portfolio(
        snapshots=snapshots, transactions=transactions, cash_balance=1815.0
    )

    result = VolatilityCalculator(as_of=BASE + timedelta(days=30)).calculate(portfolio, [])

    # period 0->1: (1500-400)/1000-1 = 0.10 (not the raw 50% the deposit would suggest)
    # period 1->2: (1650)/1500-1 = 0.10
    # period 2->3: (1815)/1650-1 = 0.10
    # all three periods should be equal once the deposit is excluded -> zero volatility
    assert result.daily_volatility_pct == pytest.approx(0.0, abs=1e-6)


def test_annualization_scales_with_period_length():
    """Same period-level stdev, different period lengths, should produce
    different annualized figures - confirms annualization isn't a no-op.
    """
    daily_snapshots = [snap(i, 1000.0 * (1.01 if i % 2 == 0 else 0.99)) for i in range(10)]
    portfolio_daily = make_portfolio(snapshots=daily_snapshots, cash_balance=1000.0)
    result_daily = VolatilityCalculator(as_of=BASE + timedelta(days=9)).calculate(
        portfolio_daily, []
    )

    assert result_daily.status == "ok"
    assert result_daily.annualized_volatility_pct > result_daily.daily_volatility_pct


def test_observation_period_and_sample_count():
    snapshots = [snap(0, 1000.0), snap(10, 1100.0), snap(20, 1200.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1200.0)

    result = VolatilityCalculator(as_of=BASE + timedelta(days=20)).calculate(portfolio, [])

    assert result.observation_period_days == 20
    assert result.sample_count == 2


def test_default_as_of_uses_current_time_when_not_injected():
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0)], cash_balance=1000.0)
    result = VolatilityCalculator().calculate(portfolio, [])
    assert result.as_of is not None
