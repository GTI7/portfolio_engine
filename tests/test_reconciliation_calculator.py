from datetime import datetime, timedelta

from engine.calculators.reconciliation_calculator import ReconciliationCalculator
from engine.models import Holding, Portfolio, Position, Quote, Transaction, TransactionType

BASE_DATE = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def txn(offset_days, type_, **kwargs):
    defaults = dict(
        id=f"txn-{offset_days}-{type_.value}-{kwargs.get('symbol', 'cash')}",
        portfolio_id="demo",
        type=type_,
        date=BASE_DATE + timedelta(days=offset_days),
        currency="USD",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def make_position(symbol, shares, avg_price, currency="USD", type_="stock"):
    holding = Holding(
        symbol=symbol, shares=shares, avg_price=avg_price, currency=currency, type=type_
    )
    quote = Quote(symbol=symbol, price=avg_price, currency=currency)
    market_value = avg_price * shares
    return Position(
        holding=holding,
        quote=quote,
        market_value=market_value,
        market_value_base=market_value,
        cost_basis=market_value,
        cost_basis_base=market_value,
        unrealized_gain=0.0,
        gain_pct=0.0,
        day_change_pct=0.0,
    )


def make_portfolio(transactions=None, cash_balance=0.0, base_currency="USD"):
    return Portfolio(
        id="demo",
        name="Demo",
        base_currency=base_currency,
        cash_balance=cash_balance,
        transactions=transactions or [],
    )


def test_no_transactions_returns_no_data():
    portfolio = make_portfolio(transactions=[], cash_balance=1000.0)
    positions = [make_position("AAPL", 10, 100.0)]

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "no_data"
    assert result.discrepancies == []
    assert result.transactions_considered == 0


def test_matching_state_is_ok():
    transactions = [
        txn(0, TransactionType.DEPOSIT, amount=2000.0),
        txn(1, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1000.0)
    positions = [make_position("AAPL", 10, 100.0)]

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "ok"
    assert result.discrepancies == []
    assert result.transactions_considered == 2


def test_mismatched_shares_produces_discrepancy():
    transactions = [
        txn(0, TransactionType.DEPOSIT, amount=2000.0),
        txn(1, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1000.0)
    # declared holdings say 15 shares, but the log only accounts for 10
    positions = [make_position("AAPL", 15, 100.0)]

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "discrepancy"
    shares_discrepancy = next(d for d in result.discrepancies if d.field == "shares")
    assert shares_discrepancy.symbol == "AAPL"
    assert shares_discrepancy.declared == 15.0
    assert shares_discrepancy.reconstructed == 10.0
    assert shares_discrepancy.difference == 5.0


def test_mismatched_cash_balance_produces_discrepancy():
    transactions = [txn(0, TransactionType.DEPOSIT, amount=1000.0)]
    portfolio = make_portfolio(transactions=transactions, cash_balance=5000.0)  # wrong value
    positions = []

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "discrepancy"
    cash_discrepancy = next(d for d in result.discrepancies if d.field == "cash_balance")
    assert cash_discrepancy.symbol is None
    assert cash_discrepancy.declared == 5000.0
    assert cash_discrepancy.reconstructed == 1000.0


def test_mismatched_avg_price_produces_discrepancy():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0)
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=0.0)
    positions = [make_position("AAPL", 10, 999.0)]  # wrong avg_price, should be 100

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "discrepancy"
    price_discrepancy = next(d for d in result.discrepancies if d.field == "avg_price")
    assert price_discrepancy.declared == 999.0
    assert price_discrepancy.reconstructed == 100.0


def test_tiny_rounding_difference_does_not_trigger_discrepancy():
    transactions = [txn(0, TransactionType.DEPOSIT, amount=1000.0)]
    # off by less than TOLERANCE (0.01)
    portfolio = make_portfolio(transactions=transactions, cash_balance=1000.005)
    positions = []

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "ok"


def test_difference_just_over_tolerance_triggers_discrepancy():
    transactions = [txn(0, TransactionType.DEPOSIT, amount=1000.0)]
    portfolio = make_portfolio(transactions=transactions, cash_balance=1000.02)
    positions = []

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "discrepancy"


def test_symbol_only_in_transactions_not_in_declared_holdings_is_a_discrepancy():
    # log says AAPL was bought, but holdings.yaml doesn't declare it at all
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0)
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=0.0)
    positions = []

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "discrepancy"
    shares_discrepancy = next(d for d in result.discrepancies if d.symbol == "AAPL")
    assert shares_discrepancy.declared == 0.0
    assert shares_discrepancy.reconstructed == 10.0


def test_symbol_only_in_declared_holdings_not_in_transactions_is_a_discrepancy():
    # declared holdings include MSFT, but no transaction ever recorded it
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0)
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=0.0)
    positions = [make_position("AAPL", 10, 100.0), make_position("MSFT", 10, 300.0)]

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.status == "discrepancy"
    msft_discrepancy = next(d for d in result.discrepancies if d.symbol == "MSFT")
    assert msft_discrepancy.declared == 10.0
    assert msft_discrepancy.reconstructed == 0.0


def test_transactions_considered_counts_all_not_just_relevant_ones():
    transactions = [
        txn(0, TransactionType.DEPOSIT, amount=1000.0),
        txn(1, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(2, TransactionType.DIVIDEND, symbol="AAPL", amount=5.0),
    ]
    portfolio = make_portfolio(transactions=transactions, cash_balance=5.0)
    positions = [make_position("AAPL", 10, 100.0)]

    result = ReconciliationCalculator().calculate(portfolio, positions)

    assert result.transactions_considered == 3
