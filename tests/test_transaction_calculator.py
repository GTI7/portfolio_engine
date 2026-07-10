from datetime import datetime, timedelta

from engine.calculators.transaction_calculator import RECENT_LIMIT, TransactionCalculator
from engine.models import Portfolio, Transaction, TransactionType

BASE_DATE = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def txn(offset_days, type_=TransactionType.DEPOSIT, **kwargs):
    defaults = dict(
        id=f"txn-{offset_days}",
        portfolio_id="demo",
        type=type_,
        date=BASE_DATE + timedelta(days=offset_days),
        currency="USD",
        amount=100.0,
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def make_portfolio(transactions):
    return Portfolio(id="demo", name="Demo", transactions=transactions)


def test_empty_log_count_zero():
    result = TransactionCalculator().calculate(make_portfolio([]), [])
    assert result.count == 0
    assert result.recent == []


def test_count_matches_transaction_count():
    transactions = [txn(0), txn(1), txn(2)]
    result = TransactionCalculator().calculate(make_portfolio(transactions), [])
    assert result.count == 3


def test_recent_ordered_newest_first():
    early = txn(0)
    middle = txn(5)
    late = txn(10)
    # deliberately passed in non-chronological order
    result = TransactionCalculator().calculate(make_portfolio([middle, early, late]), [])

    assert result.recent == [late, middle, early]


def test_recent_truncated_to_limit():
    transactions = [txn(i) for i in range(RECENT_LIMIT + 5)]
    result = TransactionCalculator().calculate(make_portfolio(transactions), [])

    assert len(result.recent) == RECENT_LIMIT
    assert result.count == RECENT_LIMIT + 5  # count is NOT truncated, only `recent` is
    # the most recent RECENT_LIMIT entries, newest first
    assert result.recent[0].id == f"txn-{RECENT_LIMIT + 4}"


def test_fewer_than_limit_returns_all():
    transactions = [txn(0), txn(1)]
    result = TransactionCalculator().calculate(make_portfolio(transactions), [])
    assert len(result.recent) == 2
