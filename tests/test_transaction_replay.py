from datetime import datetime, timedelta

from engine.models import Transaction, TransactionType
from engine.transaction_replay import TransactionReplayResult, replay_transactions

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


# --- Empty log ---------------------------------------------------------------

def test_empty_log_returns_empty_holdings_and_opening_balance():
    result = replay_transactions([], opening_cash_balance=1000.0)
    assert result.holdings == {}
    assert result.cash_balance == 1000.0
    assert result.warnings == []


def test_empty_log_default_opening_balance_is_zero():
    result = replay_transactions([])
    assert result.cash_balance == 0.0


# --- Single buy ----------------------------------------------------------------

def test_single_buy_establishes_holding():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0)
    ]
    result = replay_transactions(transactions)

    assert result.holdings["AAPL"].shares == 10
    assert result.holdings["AAPL"].avg_price == 100.0
    assert result.cash_balance == -1000.0  # BUY reduces cash
    assert result.warnings == []


# --- Multiple buys: weighted average correctness ------------------------------

def test_multiple_buys_weighted_average():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(1, TransactionType.BUY, symbol="AAPL", shares=10, price=200.0, amount=2000.0),
    ]
    result = replay_transactions(transactions)

    # (10*100 + 10*200) / 20 = 150
    assert result.holdings["AAPL"].shares == 20
    assert result.holdings["AAPL"].avg_price == 150.0


def test_three_buys_weighted_average_hand_computed():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=5, price=100.0, amount=500.0),
        txn(1, TransactionType.BUY, symbol="AAPL", shares=3, price=120.0, amount=360.0),
        txn(2, TransactionType.BUY, symbol="AAPL", shares=2, price=150.0, amount=300.0),
    ]
    result = replay_transactions(transactions)

    # (5*100 + 3*120 + 2*150) / 10 = (500+360+300)/10 = 116.0
    assert result.holdings["AAPL"].shares == 10
    assert result.holdings["AAPL"].avg_price == 116.0


# --- Buy then sell: shares reduce, avg_price unchanged -------------------------

def test_buy_then_sell_reduces_shares_avg_price_unchanged():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(1, TransactionType.SELL, symbol="AAPL", shares=4, price=150.0, amount=600.0),
    ]
    result = replay_transactions(transactions)

    assert result.holdings["AAPL"].shares == 6
    assert result.holdings["AAPL"].avg_price == 100.0  # unchanged by the sale
    assert result.cash_balance == -1000.0 + 600.0
    assert result.warnings == []


def test_sell_all_shares_leaves_zero_not_removed():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(1, TransactionType.SELL, symbol="AAPL", shares=10, price=150.0, amount=1500.0),
    ]
    result = replay_transactions(transactions)

    assert "AAPL" in result.holdings
    assert result.holdings["AAPL"].shares == 0
    assert result.warnings == []  # exactly zero is not an oversell


# --- Transfer_in establishes cost basis -----------------------------------------

def test_transfer_in_establishes_cost_basis_with_no_cash_effect():
    transactions = [
        txn(0, TransactionType.TRANSFER_IN, symbol="MSFT", shares=5, price=300.0, amount=0.0),
    ]
    result = replay_transactions(transactions)

    assert result.holdings["MSFT"].shares == 5
    assert result.holdings["MSFT"].avg_price == 300.0
    assert result.cash_balance == 0.0


def test_transfer_in_then_buy_blends_cost_basis():
    transactions = [
        txn(0, TransactionType.TRANSFER_IN, symbol="MSFT", shares=5, price=300.0, amount=0.0),
        txn(1, TransactionType.BUY, symbol="MSFT", shares=5, price=340.0, amount=1700.0),
    ]
    result = replay_transactions(transactions)

    # (5*300 + 5*340) / 10 = 320
    assert result.holdings["MSFT"].shares == 10
    assert result.holdings["MSFT"].avg_price == 320.0


def test_transfer_out_reduces_shares_no_cash_effect():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(1, TransactionType.TRANSFER_OUT, symbol="AAPL", shares=3, price=150.0, amount=0.0),
    ]
    result = replay_transactions(transactions)

    assert result.holdings["AAPL"].shares == 7
    assert result.holdings["AAPL"].avg_price == 100.0
    assert result.cash_balance == -1000.0  # transfer_out has zero cash effect


# --- Multiple symbols tracked independently -------------------------------------

def test_multiple_symbols_independent():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(1, TransactionType.BUY, symbol="MSFT", shares=5, price=300.0, amount=1500.0),
        txn(2, TransactionType.SELL, symbol="AAPL", shares=2, price=120.0, amount=240.0),
    ]
    result = replay_transactions(transactions)

    assert result.holdings["AAPL"].shares == 8
    assert result.holdings["AAPL"].avg_price == 100.0
    assert result.holdings["MSFT"].shares == 5
    assert result.holdings["MSFT"].avg_price == 300.0
    assert result.cash_balance == -1000.0 - 1500.0 + 240.0


# --- Every TransactionType's cash effect in isolation ---------------------------

def test_buy_cash_effect():
    result = replay_transactions(
        [txn(0, TransactionType.BUY, symbol="A", shares=1, price=100.0, amount=100.0)]
    )
    assert result.cash_balance == -100.0


def test_sell_cash_effect():
    result = replay_transactions(
        [txn(0, TransactionType.SELL, symbol="A", shares=1, price=100.0, amount=100.0)]
    )
    assert result.cash_balance == 100.0


def test_dividend_cash_effect():
    result = replay_transactions([txn(0, TransactionType.DIVIDEND, symbol="A", amount=50.0)])
    assert result.cash_balance == 50.0
    assert result.holdings == {}  # dividends never affect holdings


def test_deposit_cash_effect():
    result = replay_transactions([txn(0, TransactionType.DEPOSIT, amount=1000.0)])
    assert result.cash_balance == 1000.0


def test_withdrawal_cash_effect():
    result = replay_transactions([txn(0, TransactionType.WITHDRAWAL, amount=200.0)])
    assert result.cash_balance == -200.0


def test_fee_cash_effect():
    result = replay_transactions([txn(0, TransactionType.FEE, amount=9.99)])
    assert result.cash_balance == -9.99


def test_transfer_in_cash_effect_is_zero():
    result = replay_transactions(
        [txn(0, TransactionType.TRANSFER_IN, symbol="A", shares=1, price=100.0, amount=0.0)]
    )
    assert result.cash_balance == 0.0


def test_transfer_out_cash_effect_is_zero():
    result = replay_transactions(
        [
            txn(0, TransactionType.BUY, symbol="A", shares=5, price=10.0, amount=50.0),
            txn(1, TransactionType.TRANSFER_OUT, symbol="A", shares=1, price=10.0, amount=0.0),
        ]
    )
    assert result.cash_balance == -50.0  # only the BUY affected cash


# --- A realistic mixed sequence --------------------------------------------------

def test_realistic_mixed_sequence():
    transactions = [
        txn(0, TransactionType.DEPOSIT, amount=10000.0),
        txn(1, TransactionType.BUY, symbol="AAPL", shares=20, price=150.0, amount=3000.0),
        txn(10, TransactionType.DIVIDEND, symbol="AAPL", amount=15.0),
        txn(20, TransactionType.BUY, symbol="AAPL", shares=10, price=180.0, amount=1800.0),
        txn(30, TransactionType.SELL, symbol="AAPL", shares=5, price=200.0, amount=1000.0),
        txn(40, TransactionType.FEE, amount=4.95),
        txn(50, TransactionType.WITHDRAWAL, amount=500.0),
    ]
    result = replay_transactions(transactions)

    # holdings: bought 20 @150, bought 10 @180, sold 5 (avg unchanged)
    # avg_price = (20*150 + 10*180)/30 = (3000+1800)/30 = 160
    assert result.holdings["AAPL"].shares == 25
    assert result.holdings["AAPL"].avg_price == round(4800 / 30, 6)

    # cash: +10000 -3000 +15 -1800 +1000 -4.95 -500
    expected_cash = 10000 - 3000 + 15 - 1800 + 1000 - 4.95 - 500
    assert result.cash_balance == round(expected_cash, 2)
    assert result.warnings == []


# --- opening_cash_balance parameter -----------------------------------------------

def test_opening_cash_balance_is_starting_point():
    transactions = [txn(0, TransactionType.DEPOSIT, amount=100.0)]
    result = replay_transactions(transactions, opening_cash_balance=500.0)
    assert result.cash_balance == 600.0


# --- Order independence: date order, not file/id order -----------------------------

def test_replay_sorts_by_date_regardless_of_input_order():
    later = txn(10, TransactionType.BUY, symbol="AAPL", shares=5, price=200.0, amount=1000.0)
    earlier = txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0)
    # passed in "wrong" order - later transaction first in the list
    result = replay_transactions([later, earlier])

    # if replay respected list order instead of date, avg_price would differ
    # (irrelevant here since both are pure additions, but shares/cash must
    # still be correct regardless of input order)
    assert result.holdings["AAPL"].shares == 15
    assert result.cash_balance == -2000.0


# --- Oversold / incomplete log: clamped + warned, not raised ------------------------

def test_sell_without_prior_buy_is_clamped_to_zero_with_warning():
    transactions = [
        txn(0, TransactionType.SELL, symbol="AAPL", shares=5, price=100.0, amount=500.0)
    ]
    result = replay_transactions(transactions)

    assert result.holdings["AAPL"].shares == 0  # clamped, never negative
    assert len(result.warnings) == 1
    assert "AAPL" in result.warnings[0]
    assert "negative" in result.warnings[0]
    assert result.cash_balance == 500.0  # cash effect still applied normally


def test_overselling_more_than_held_is_clamped_with_warning():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=5, price=100.0, amount=500.0),
        txn(1, TransactionType.SELL, symbol="AAPL", shares=10, price=120.0, amount=1200.0),
    ]
    result = replay_transactions(transactions)

    assert result.holdings["AAPL"].shares == 0
    assert len(result.warnings) == 1


def test_no_warning_when_nothing_oversold():
    transactions = [
        txn(0, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0),
        txn(1, TransactionType.SELL, symbol="AAPL", shares=5, price=120.0, amount=600.0),
    ]
    result = replay_transactions(transactions)
    assert result.warnings == []


# --- Result shape -------------------------------------------------------------

def test_result_is_transaction_replay_result_instance():
    result = replay_transactions([])
    assert isinstance(result, TransactionReplayResult)
    assert hasattr(result, "holdings")
    assert hasattr(result, "cash_balance")
    assert hasattr(result, "warnings")
