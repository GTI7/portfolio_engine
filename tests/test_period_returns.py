from datetime import datetime, timedelta

import pytest

from engine.models import (
    Holding,
    Portfolio,
    Position,
    Quote,
    Snapshot,
    Transaction,
    TransactionType,
)
from engine.period_returns import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_NO_DATA,
    STATUS_NOT_COMPUTABLE,
    STATUS_OK,
    compute_period_returns,
)

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
    result = compute_period_returns(make_portfolio(), [], as_of=BASE)
    assert result.status == STATUS_NO_DATA
    assert result.periods == []


def test_one_snapshot_no_elapsed_time_is_insufficient_data():
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0)])
    result = compute_period_returns(portfolio, [], as_of=BASE)
    assert result.status == STATUS_INSUFFICIENT_DATA


def test_two_snapshots_produces_one_period_with_correct_return():
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0), snap(30, 1100.0)])
    result = compute_period_returns(portfolio, [], as_of=BASE + timedelta(days=30))

    assert result.status == STATUS_OK
    assert len(result.periods) == 1
    assert result.periods[0].return_fraction == pytest.approx(0.10)
    assert result.periods[0].start == BASE
    assert result.periods[0].end == BASE + timedelta(days=30)


def test_deposit_excluded_from_period_return():
    portfolio = make_portfolio(
        snapshots=[snap(0, 1000.0), snap(30, 1500.0)],
        transactions=[txn(15, TransactionType.DEPOSIT, amount=400.0)],
    )
    result = compute_period_returns(portfolio, [], as_of=BASE + timedelta(days=30))

    # (1500 - 400) / 1000 - 1 = 0.10
    assert result.periods[0].return_fraction == pytest.approx(0.10)


def test_zero_value_period_start_is_not_computable():
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0), snap(30, 0.0), snap(60, 500.0)])
    result = compute_period_returns(portfolio, [], as_of=BASE + timedelta(days=60))

    assert result.status == STATUS_NOT_COMPUTABLE
    assert len(result.periods) == 1  # the first valid period is preserved


def test_synthetic_final_period_uses_current_positions_value():
    holding = Holding(symbol="AAPL", shares=10, avg_price=100.0, currency="USD", type="stock")
    quote = Quote(symbol="AAPL", price=110.0, currency="USD")
    position = Position(
        holding=holding,
        quote=quote,
        market_value=1100.0,
        market_value_base=1100.0,
        cost_basis=1000.0,
        cost_basis_base=1000.0,
        unrealized_gain=100.0,
        gain_pct=10.0,
        day_change_pct=0.0,
    )
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0)], cash_balance=0.0)
    as_of = BASE + timedelta(days=10)

    result = compute_period_returns(portfolio, [position], as_of=as_of)

    assert result.status == STATUS_OK
    assert len(result.periods) == 1
    assert result.periods[0].end == as_of
    assert result.periods[0].return_fraction == pytest.approx(0.10)  # 1000 -> 1100


def test_multiple_periods_each_correct():
    portfolio = make_portfolio(
        snapshots=[snap(0, 1000.0), snap(10, 1100.0), snap(20, 1210.0)]
    )
    result = compute_period_returns(portfolio, [], as_of=BASE + timedelta(days=20))

    assert result.status == STATUS_OK
    assert len(result.periods) == 2
    assert result.periods[0].return_fraction == pytest.approx(0.10)
    assert result.periods[1].return_fraction == pytest.approx(0.10)
