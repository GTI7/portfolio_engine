from datetime import UTC, datetime, timedelta

import pytest

from engine.calculators.mwr_calculator import MwrCalculator
from engine.models import Holding, Portfolio, Position, Quote, Transaction, TransactionType

BASE_DATE = datetime.fromisoformat("2025-01-01T00:00:00+00:00")


def txn(offset_days, type_, **kwargs):
    defaults = dict(
        id=f"txn-{offset_days}-{type_.value}",
        portfolio_id="demo",
        type=type_,
        date=BASE_DATE + timedelta(days=offset_days),
        currency="USD",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def make_position(symbol, shares, price):
    holding = Holding(symbol=symbol, shares=shares, avg_price=price, currency="USD", type="stock")
    quote = Quote(symbol=symbol, price=price, currency="USD")
    value = shares * price
    return Position(
        holding=holding,
        quote=quote,
        market_value=value,
        market_value_base=value,
        cost_basis=value,
        cost_basis_base=value,
        unrealized_gain=0.0,
        gain_pct=0.0,
        day_change_pct=0.0,
    )


def make_portfolio(transactions=None, cash_balance=0.0):
    return Portfolio(
        id="demo", name="Demo", cash_balance=cash_balance, transactions=transactions or []
    )


AS_OF = BASE_DATE + timedelta(days=365)


def test_no_transactions_at_all_is_no_data():
    portfolio = make_portfolio(transactions=[])
    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, [])
    assert result.status == "no_data"
    assert result.rate_pct is None


def test_only_internal_transactions_is_no_data():
    """BUY/SELL/DIVIDEND/FEE alone contribute zero external cash flows -
    per ADR-0011, this must not be treated as computable.
    """
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(10, TransactionType.DIVIDEND, symbol="AAPL", amount=5.0),
        txn(20, TransactionType.FEE, amount=1.0),
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=4.0)
    positions = [make_position("AAPL", 10, 150.0)]

    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, positions)
    assert result.status == "no_data"


def test_deposit_and_growth_computes_ok():
    transactions = [txn(0, TransactionType.DEPOSIT, amount=1000.0)]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1100.0)

    # AS_OF is 365 days after BASE_DATE - 1000 -> 1100 in exactly one year
    # is exactly 10%.
    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.rate_pct == pytest.approx(10.0, abs=1e-2)
    assert result.cash_flow_count == 2


def test_withdrawal_counted_as_positive_external_flow():
    transactions = [
        txn(0, TransactionType.DEPOSIT, amount=2000.0),
        txn(180, TransactionType.WITHDRAWAL, amount=500.0),
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1600.0)

    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.cash_flow_count == 3  # deposit + withdrawal + terminal


def test_transfer_in_valued_at_shares_times_price_not_zero():
    """Per ADR-0011: TRANSFER_IN's Transaction.amount is 0.0, but the
    external cash flow used for XIRR must be shares*price, not 0 - else a
    transfer would masquerade as investment growth.
    """
    transactions = [
        txn(0, TransactionType.TRANSFER_IN, symbol="MSFT", shares=10, price=300.0, amount=0.0),
    ]
    # if transferred-in value (3000) were treated as growth from a 0 base,
    # this would be mathematically undefined; with the correct -3000 flow
    # and a terminal value of 3000, the return should be ~0%.
    portfolio = make_portfolio(transactions=transactions, cash_balance=0.0)
    positions = [make_position("MSFT", 10, 300.0)]  # unchanged value - true 0% return

    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, positions)

    assert result.status == "ok"
    assert result.rate_pct == pytest.approx(0.0, abs=1e-2)


def test_transfer_out_counted_as_positive_external_flow():
    transactions = [
        txn(0, TransactionType.DEPOSIT, amount=1000.0),
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(180, TransactionType.TRANSFER_OUT, symbol="AAPL", shares=5, price=110.0, amount=0.0),
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=0.0)
    positions = [make_position("AAPL", 5, 120.0)]

    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, positions)

    assert result.status == "ok"
    assert result.cash_flow_count == 3  # deposit + transfer_out + terminal (BUY excluded)


def test_buy_sell_dividend_fee_never_appear_as_flows():
    transactions = [
        txn(0, TransactionType.DEPOSIT, amount=1000.0),
        txn(1, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(2, TransactionType.SELL, symbol="AAPL", shares=2, price=110.0, amount=220.0),
        txn(3, TransactionType.DIVIDEND, symbol="AAPL", amount=5.0),
        txn(4, TransactionType.FEE, amount=1.0),
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=224.0)
    positions = [make_position("AAPL", 8, 120.0)]

    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, positions)

    # only DEPOSIT + terminal = 2 flows, despite 5 transactions total
    assert result.cash_flow_count == 2


def test_all_flows_same_date_is_insufficient_data():
    same_day = BASE_DATE
    transactions = [
        Transaction(
            id="t1",
            portfolio_id="demo",
            type=TransactionType.DEPOSIT,
            date=same_day,
            currency="USD",
            amount=1000.0,
        )
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1000.0)

    # as_of matches the single transaction's date exactly - no time spread
    result = MwrCalculator(as_of=same_day).calculate(portfolio, [])

    assert result.status == "insufficient_data"


def test_no_sign_change_is_insufficient_data():
    """A deposit with a terminal value of exactly 0 (e.g. total loss and
    no other flows) would leave every flow non-positive - no root exists,
    should be classified before ever calling xirr().
    """
    transactions = [txn(0, TransactionType.DEPOSIT, amount=1000.0)]
    portfolio = make_portfolio(transactions=transactions, cash_balance=0.0)

    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, [])

    assert result.status == "insufficient_data"


def test_default_as_of_uses_current_time_when_not_injected():
    transactions = [txn(0, TransactionType.DEPOSIT, amount=1000.0)]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1000.0)

    before = datetime.now(UTC)
    result = MwrCalculator().calculate(portfolio, [])  # no as_of injected
    after = datetime.now(UTC)

    assert result.as_of is not None
    assert before <= result.as_of <= after


def test_rate_pct_is_percentage_not_fraction():
    transactions = [txn(0, TransactionType.DEPOSIT, amount=1000.0)]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1100.0)

    result = MwrCalculator(as_of=AS_OF).calculate(portfolio, [])

    # 10% return should be reported as 10.0, not 0.10
    assert result.rate_pct > 1.0
    assert result.rate_pct == pytest.approx(10.0, abs=1e-2)
