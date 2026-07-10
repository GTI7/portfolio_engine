from datetime import datetime, timedelta

import pytest

from engine.calculators.dividend_calculator import DividendCalculator
from engine.models import Holding, Portfolio, Position, Quote, Transaction, TransactionType

BASE = datetime.fromisoformat("2025-01-01T00:00:00+00:00")


def txn(offset_days, type_=TransactionType.DIVIDEND, **kwargs):
    defaults = dict(
        id=f"txn-{offset_days}",
        portfolio_id="demo",
        type=type_,
        date=BASE + timedelta(days=offset_days),
        currency="USD",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def make_position(symbol, shares, avg_price, price):
    holding = Holding(
        symbol=symbol, shares=shares, avg_price=avg_price, currency="USD", type="stock"
    )
    quote = Quote(symbol=symbol, price=price, currency="USD")
    value = shares * price
    cost = shares * avg_price
    return Position(
        holding=holding,
        quote=quote,
        market_value=value,
        market_value_base=value,
        cost_basis=cost,
        cost_basis_base=cost,
        unrealized_gain=value - cost,
        gain_pct=0.0,
        day_change_pct=0.0,
    )


def make_portfolio(transactions=None):
    return Portfolio(id="demo", name="Demo", transactions=transactions or [])


def test_no_dividends_is_no_data():
    result = DividendCalculator(as_of=BASE).calculate(make_portfolio(), [])
    assert result.status == "no_data"


def test_lifetime_sums_all_dividends():
    transactions = [
        txn(0, symbol="AAPL", amount=10.0),
        txn(30, symbol="AAPL", amount=15.0),
        txn(60, symbol="AAPL", amount=20.0),
    ]
    result = DividendCalculator(as_of=BASE + timedelta(days=90)).calculate(
        make_portfolio(transactions), []
    )
    assert result.status == "ok"
    assert result.lifetime == 45.0


def test_rolling_12_months_excludes_older_dividends():
    transactions = [
        txn(0, symbol="AAPL", amount=100.0),   # well before as_of - excluded from rolling
        txn(400, symbol="AAPL", amount=10.0),
        txn(500, symbol="AAPL", amount=15.0),
    ]
    as_of = BASE + timedelta(days=700)  # 300, 200 days after the last two -> within 365
    result = DividendCalculator(as_of=as_of).calculate(make_portfolio(transactions), [])

    assert result.lifetime == 125.0
    assert result.rolling_12_months == 25.0  # only the two recent ones


def test_current_year_only_counts_this_calendar_year():
    transactions = [
        txn(0, symbol="AAPL", amount=10.0),      # 2025-01-01
        txn(400, symbol="AAPL", amount=20.0),     # 2026-02-04 (next year)
    ]
    as_of = datetime.fromisoformat("2026-06-01T00:00:00+00:00")
    result = DividendCalculator(as_of=as_of).calculate(make_portfolio(transactions), [])

    assert result.current_year == 20.0
    assert result.lifetime == 30.0


def test_average_monthly_dividend():
    # two dividends spread over exactly 12 months (365 days), 12 total
    transactions = [txn(0, symbol="AAPL", amount=6.0), txn(365, symbol="AAPL", amount=6.0)]
    as_of = BASE + timedelta(days=365)
    result = DividendCalculator(as_of=as_of).calculate(make_portfolio(transactions), [])

    # lifetime=12 over ~365/30.44=~11.99 months -> ~1.0/month
    assert result.average_monthly_dividend == pytest.approx(1.0, abs=0.05)


def test_dividend_yield_uses_invested_capital():
    transactions = [txn(0, symbol="AAPL", amount=50.0)]
    positions = [make_position("AAPL", 10, 100.0, 150.0)]  # cost_basis = 1000
    as_of = BASE + timedelta(days=30)
    result = DividendCalculator(as_of=as_of).calculate(make_portfolio(transactions), positions)

    assert result.dividend_yield_pct == pytest.approx(5.0, abs=1e-4)  # 50/1000 * 100


def test_dividend_yield_none_when_no_positions():
    transactions = [txn(0, symbol="AAPL", amount=50.0)]
    result = DividendCalculator(as_of=BASE + timedelta(days=1)).calculate(
        make_portfolio(transactions), []
    )
    assert result.dividend_yield_pct is None


def test_dividends_after_as_of_are_ignored():
    """A dividend dated in the future relative to as_of shouldn't count at
    all - not in lifetime, not anywhere. Found while writing this test:
    the first implementation only applied this filter to rolling/current-
    year, not lifetime/average_monthly - fixed before this test was added.
    """
    transactions = [txn(100, symbol="AAPL", amount=999.0)]
    result = DividendCalculator(as_of=BASE).calculate(make_portfolio(transactions), [])
    assert result.status == "no_data"  # the only dividend is in the future


def test_future_dividend_does_not_leak_into_lifetime_when_others_exist():
    transactions = [
        txn(0, symbol="AAPL", amount=10.0),
        txn(100, symbol="AAPL", amount=999.0),  # after as_of
    ]
    result = DividendCalculator(as_of=BASE + timedelta(days=1)).calculate(
        make_portfolio(transactions), []
    )
    assert result.lifetime == 10.0
