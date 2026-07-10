from datetime import datetime

import pytest

from engine.models import CASH_EFFECT_SIGN, Portfolio, Transaction, TransactionType


def dt(s="2026-03-15T14:30:00+00:00"):
    return datetime.fromisoformat(s)


CASH_ONLY_TYPES = [TransactionType.DEPOSIT, TransactionType.WITHDRAWAL, TransactionType.FEE]
TRANSFER_TYPES = [TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT]


def make_transaction(**overrides):
    defaults = dict(
        id="txn-1",
        portfolio_id="demo",
        type=TransactionType.BUY,
        date=dt(),
        currency="USD",
        amount=1000.0,
        symbol="AAPL",
        shares=10.0,
        price=100.0,
    )
    defaults.update(overrides)
    return Transaction(**defaults)


# --- BUY -----------------------------------------------------------------

def test_buy_valid():
    txn = make_transaction(
        type=TransactionType.BUY, symbol="AAPL", shares=10, price=100, amount=1000
    )
    assert txn.type is TransactionType.BUY


def test_buy_requires_symbol():
    with pytest.raises(ValueError, match="requires symbol"):
        make_transaction(type=TransactionType.BUY, symbol=None)


def test_buy_requires_positive_shares():
    with pytest.raises(ValueError, match="requires shares"):
        make_transaction(type=TransactionType.BUY, shares=0)
    with pytest.raises(ValueError, match="requires shares"):
        make_transaction(type=TransactionType.BUY, shares=-5)


def test_buy_requires_positive_price():
    with pytest.raises(ValueError, match="requires price"):
        make_transaction(type=TransactionType.BUY, price=0)


def test_buy_requires_positive_amount():
    with pytest.raises(ValueError, match="requires amount > 0"):
        make_transaction(type=TransactionType.BUY, amount=0)


# --- SELL ------------------------------------------------------------------

def test_sell_valid():
    txn = make_transaction(
        type=TransactionType.SELL, symbol="AAPL", shares=5, price=120, amount=600
    )
    assert txn.type is TransactionType.SELL


def test_sell_requires_symbol_shares_price():
    with pytest.raises(ValueError):
        make_transaction(type=TransactionType.SELL, symbol=None)
    with pytest.raises(ValueError):
        make_transaction(type=TransactionType.SELL, shares=None)
    with pytest.raises(ValueError):
        make_transaction(type=TransactionType.SELL, price=None)


# --- DIVIDEND ----------------------------------------------------------------

def test_dividend_valid():
    txn = make_transaction(
        type=TransactionType.DIVIDEND, symbol="AAPL", shares=None, price=None, amount=12.5
    )
    assert txn.type is TransactionType.DIVIDEND


def test_dividend_requires_symbol():
    with pytest.raises(ValueError, match="dividend requires symbol"):
        make_transaction(
            type=TransactionType.DIVIDEND, symbol=None, shares=None, price=None, amount=12.5
        )


def test_dividend_rejects_shares():
    with pytest.raises(ValueError, match="must not have shares"):
        make_transaction(
            type=TransactionType.DIVIDEND, symbol="AAPL", shares=1, price=None, amount=12.5
        )


def test_dividend_rejects_price():
    with pytest.raises(ValueError, match="must not have price"):
        make_transaction(
            type=TransactionType.DIVIDEND, symbol="AAPL", shares=None, price=1, amount=12.5
        )


def test_dividend_requires_positive_amount():
    with pytest.raises(ValueError, match="requires amount > 0"):
        make_transaction(
            type=TransactionType.DIVIDEND, symbol="AAPL", shares=None, price=None, amount=0
        )


# --- DEPOSIT / WITHDRAWAL / FEE (identical shape rules) ----------------------

@pytest.mark.parametrize("txn_type", CASH_ONLY_TYPES)
def test_cash_only_types_valid(txn_type):
    txn = make_transaction(type=txn_type, symbol=None, shares=None, price=None, amount=500)
    assert txn.type is txn_type


@pytest.mark.parametrize("txn_type", CASH_ONLY_TYPES)
def test_cash_only_types_reject_symbol(txn_type):
    with pytest.raises(ValueError, match="must not have a symbol"):
        make_transaction(type=txn_type, symbol="AAPL", shares=None, price=None, amount=500)


@pytest.mark.parametrize("txn_type", CASH_ONLY_TYPES)
def test_cash_only_types_reject_shares(txn_type):
    with pytest.raises(ValueError, match="must not have shares"):
        make_transaction(type=txn_type, symbol=None, shares=1, price=None, amount=500)


@pytest.mark.parametrize("txn_type", CASH_ONLY_TYPES)
def test_cash_only_types_reject_price(txn_type):
    with pytest.raises(ValueError, match="must not have price"):
        make_transaction(type=txn_type, symbol=None, shares=None, price=1, amount=500)


@pytest.mark.parametrize("txn_type", CASH_ONLY_TYPES)
def test_cash_only_types_require_positive_amount(txn_type):
    with pytest.raises(ValueError, match="requires amount > 0"):
        make_transaction(type=txn_type, symbol=None, shares=None, price=None, amount=0)


# --- TRANSFER_IN / TRANSFER_OUT ---------------------------------------------

@pytest.mark.parametrize("txn_type", TRANSFER_TYPES)
def test_transfer_valid(txn_type):
    txn = make_transaction(type=txn_type, symbol="MSFT", shares=5, price=300, amount=0.0)
    assert txn.type is txn_type


@pytest.mark.parametrize("txn_type", TRANSFER_TYPES)
def test_transfer_requires_symbol_shares_price(txn_type):
    with pytest.raises(ValueError):
        make_transaction(type=txn_type, symbol=None, shares=5, price=300, amount=0.0)
    with pytest.raises(ValueError):
        make_transaction(type=txn_type, symbol="MSFT", shares=None, price=300, amount=0.0)
    with pytest.raises(ValueError):
        make_transaction(type=txn_type, symbol="MSFT", shares=5, price=None, amount=0.0)


@pytest.mark.parametrize("txn_type", TRANSFER_TYPES)
def test_transfer_amount_must_be_exactly_zero(txn_type):
    with pytest.raises(ValueError, match="amount == 0.0"):
        make_transaction(type=txn_type, symbol="MSFT", shares=5, price=300, amount=100.0)


# --- Universal fields --------------------------------------------------------

def test_id_required():
    with pytest.raises(ValueError, match="id is required"):
        make_transaction(id="")


def test_portfolio_id_required():
    with pytest.raises(ValueError, match="portfolio_id is required"):
        make_transaction(portfolio_id="")


def test_currency_required():
    with pytest.raises(ValueError, match="currency is required"):
        make_transaction(currency="")


def test_date_must_be_datetime():
    with pytest.raises(ValueError, match="date must be a datetime"):
        make_transaction(date="2026-03-15")  # a string, not a datetime


def test_amount_cannot_be_negative_for_any_type():
    with pytest.raises(ValueError, match="cannot be negative"):
        make_transaction(type=TransactionType.BUY, amount=-100)
    with pytest.raises(ValueError, match="cannot be negative"):
        make_transaction(
            type=TransactionType.DEPOSIT, symbol=None, shares=None, price=None, amount=-100
        )


# --- Sign-semantics table (CASH_EFFECT_SIGN) --------------------------------

def test_cash_effect_sign_covers_every_transaction_type():
    assert set(CASH_EFFECT_SIGN.keys()) == set(TransactionType)


def test_cash_effect_sign_values():
    assert CASH_EFFECT_SIGN[TransactionType.BUY] == -1
    assert CASH_EFFECT_SIGN[TransactionType.WITHDRAWAL] == -1
    assert CASH_EFFECT_SIGN[TransactionType.FEE] == -1
    assert CASH_EFFECT_SIGN[TransactionType.SELL] == 1
    assert CASH_EFFECT_SIGN[TransactionType.DEPOSIT] == 1
    assert CASH_EFFECT_SIGN[TransactionType.DIVIDEND] == 1
    assert CASH_EFFECT_SIGN[TransactionType.TRANSFER_IN] == 0
    assert CASH_EFFECT_SIGN[TransactionType.TRANSFER_OUT] == 0


# --- Portfolio.transactions (additive field) --------------------------------

def test_portfolio_defaults_transactions_to_empty_list():
    p = Portfolio(id="p1", name="Test")
    assert p.transactions == []


def test_portfolio_accepts_transactions():
    txn = make_transaction()
    p = Portfolio(id="p1", name="Test", transactions=[txn])
    assert p.transactions == [txn]


def test_pre_milestone_4_portfolio_construction_still_works():
    """The exact backward-compatibility bar this milestone is held to."""
    p = Portfolio(id="p1", name="Test", base_currency="USD", cash_balance=500.0)
    assert p.transactions == []
    assert p.cash_balance == 500.0
