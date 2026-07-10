from datetime import UTC, datetime, timedelta

import pytest

from engine.calculators.twr_calculator import TwrCalculator
from engine.models import (
    Holding,
    Portfolio,
    Position,
    Quote,
    Snapshot,
    Transaction,
    TransactionType,
)

BASE = datetime.fromisoformat("2025-01-01T00:00:00+00:00")


def snap(offset_days, value, snapshot_id=None, cash_balance=None, invested=None):
    return Snapshot(
        id=snapshot_id or f"snap-{offset_days}",
        portfolio_id="demo",
        timestamp=BASE + timedelta(days=offset_days),
        portfolio_value=value,
        cash_balance=cash_balance if cash_balance is not None else 0.0,
        invested=invested if invested is not None else value,
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


def make_portfolio(snapshots=None, transactions=None, cash_balance=0.0):
    return Portfolio(
        id="demo",
        name="Demo",
        cash_balance=cash_balance,
        snapshots=snapshots or [],
        transactions=transactions or [],
    )


# --- No snapshots -------------------------------------------------------------

def test_no_snapshots_is_no_data():
    portfolio = make_portfolio(snapshots=[])
    result = TwrCalculator(as_of=BASE + timedelta(days=30)).calculate(portfolio, [])
    assert result.status == "no_data"
    assert result.twr_pct is None


# --- One snapshot ---------------------------------------------------------------

def test_one_snapshot_with_elapsed_time_computes_using_current_value():
    snapshots = [snap(0, 1000.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1000.0)
    as_of = BASE + timedelta(days=30)

    # no positions, current computed value = cash_balance = 1000 (flat)
    result = TwrCalculator(as_of=as_of).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.twr_pct == pytest.approx(0.0, abs=1e-6)
    assert result.periods_used == 1


def test_one_snapshot_no_elapsed_time_is_insufficient_data():
    snapshots = [snap(0, 1000.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1000.0)

    # as_of exactly equal to the only snapshot's timestamp - no time spread
    result = TwrCalculator(as_of=BASE).calculate(portfolio, [])

    assert result.status == "insufficient_data"
    assert result.periods_used == 0


# --- Hand-verified two-snapshot, no-cash-flow example ---------------------------

def test_simple_two_snapshot_ten_percent_growth():
    snapshots = [snap(0, 1000.0), snap(31, 1100.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1100.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=31)).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.twr_pct == pytest.approx(10.0, abs=1e-6)
    assert result.periods_used == 1


# --- Hand-verified multi-period example with a cash flow inside a period --------

def test_multi_period_with_deposit_hand_verified():
    """
    Snapshot A (day 0): value 1000
    Deposit +500 on day 15 (inside period A->B)
    Snapshot B (day 31): value 1800
      -> period A->B return = (1800 - 500) / 1000 - 1 = 0.30 (30%)
    Snapshot C (day 59): value 1890
      -> period B->C return = (1890 - 0) / 1800 - 1 = 0.05 (5%)
    TWR = (1.30 * 1.05) - 1 = 0.365 -> 36.5%
    """
    snapshots = [snap(0, 1000.0), snap(31, 1800.0), snap(59, 1890.0)]
    transactions = [txn(15, TransactionType.DEPOSIT, amount=500.0)]
    portfolio = make_portfolio(snapshots=snapshots, transactions=transactions, cash_balance=1890.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=59)).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.twr_pct == pytest.approx(36.5, abs=1e-4)
    assert result.periods_used == 2


def test_deposit_correctly_excluded_not_counted_as_growth():
    """Without excluding the deposit, period A->B return would incorrectly
    be (1800-1000)/1000 = 80% instead of the correct 30% - this test
    fails loudly if the cash-flow exclusion logic regresses.
    """
    snapshots = [snap(0, 1000.0), snap(31, 1800.0)]
    transactions = [txn(15, TransactionType.DEPOSIT, amount=500.0)]
    portfolio = make_portfolio(snapshots=snapshots, transactions=transactions, cash_balance=1800.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=31)).calculate(portfolio, [])

    assert result.twr_pct == pytest.approx(30.0, abs=1e-4)
    assert result.twr_pct != pytest.approx(80.0, abs=1e-4)


def test_withdrawal_correctly_excluded():
    """Snapshot A: 1000. Withdraw 200 during the period. Snapshot B: 750.
    True growth = (750 - (-200)) / 1000 - 1 = 950/1000 - 1 = -0.05 (-5%),
    i.e. the portfolio actually only lost 5% despite the ending value
    being far below the starting one, once the withdrawal is accounted for.
    """
    snapshots = [snap(0, 1000.0), snap(31, 750.0)]
    transactions = [txn(15, TransactionType.WITHDRAWAL, amount=200.0)]
    portfolio = make_portfolio(snapshots=snapshots, transactions=transactions, cash_balance=750.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=31)).calculate(portfolio, [])

    assert result.twr_pct == pytest.approx(-5.0, abs=1e-4)


# --- BUY/SELL/DIVIDEND/FEE never affect TWR (internal, per ADR-0011) -----------

def test_buy_sell_dividend_fee_do_not_affect_twr():
    snapshots = [snap(0, 1000.0), snap(31, 1100.0)]
    transactions = [
        txn(5, TransactionType.BUY, symbol="AAPL", shares=1, price=100.0, amount=100.0),
        txn(10, TransactionType.DIVIDEND, symbol="AAPL", amount=5.0),
        txn(15, TransactionType.FEE, amount=1.0),
    ]
    portfolio = make_portfolio(snapshots=snapshots, transactions=transactions, cash_balance=1100.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=31)).calculate(portfolio, [])

    assert result.twr_pct == pytest.approx(10.0, abs=1e-6)  # unaffected by internal transactions


# --- Missing intervals (gaps between snapshots) --------------------------------

def test_large_gap_between_snapshots_still_computes():
    snapshots = [snap(0, 1000.0), snap(365, 1210.0)]  # a full year gap, no in-between snapshots
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1210.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=365)).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.twr_pct == pytest.approx(21.0, abs=1e-4)  # (1210-1000)/1000 = 21%
    assert result.periods_used == 1


# --- Cash flow boundary edge case: flow exactly at a snapshot's timestamp -------

def test_cash_flow_exactly_at_boundary_belongs_to_the_earlier_period():
    """A flow dated exactly at snapshot B's timestamp belongs to period
    A->B (half-open interval (t0, t1]), not B->C - confirms the boundary
    convention doesn't double-count or drop the flow.
    """
    snapshots = [snap(0, 1000.0), snap(31, 1500.0), snap(62, 1600.0)]
    # deposit dated exactly at snapshot B's timestamp (day 31)
    transactions = [txn(31, TransactionType.DEPOSIT, amount=500.0)]
    portfolio = make_portfolio(snapshots=snapshots, transactions=transactions, cash_balance=1600.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=62)).calculate(portfolio, [])

    # period A->B: (1500 - 500)/1000 - 1 = 0.0 (flat, deposit correctly
    # attributed to this period, not the next)
    # period B->C: (1600 - 0)/1500 - 1 = 0.0667
    expected = (1.0 * (1600 / 1500)) - 1
    assert result.twr_pct == pytest.approx(expected * 100, abs=1e-4)


# --- not_computable: zero begin value in a period -------------------------------

def test_zero_value_snapshot_as_period_start_is_not_computable():
    snapshots = [snap(0, 1000.0), snap(31, 0.0), snap(62, 500.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=500.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=62)).calculate(portfolio, [])

    assert result.status == "not_computable"
    # the first (valid) period was counted before hitting the bad one
    assert result.periods_used == 1


# --- Result shape / as_of ---------------------------------------------------------

def test_default_as_of_uses_current_time_when_not_injected():
    snapshots = [snap(0, 1000.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1000.0)

    before = datetime.now(UTC)
    result = TwrCalculator().calculate(portfolio, [])
    after = datetime.now(UTC)

    assert result.as_of is not None
    assert before <= result.as_of <= after


def test_twr_pct_is_cumulative_not_annualized():
    """A ~36.5% cumulative return over ~2 months should be reported as
    ~36.5, not annualized to a much larger implied yearly rate - TwrResult
    is explicitly cumulative, per its own docstring.
    """
    snapshots = [snap(0, 1000.0), snap(59, 1365.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1365.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=59)).calculate(portfolio, [])

    assert result.twr_pct == pytest.approx(36.5, abs=1e-4)


# --- Flows before the first snapshot are excluded entirely ---------------------

def test_flow_before_first_snapshot_is_excluded_not_attributed_to_period_0():
    """A deposit dated before any snapshot exists has no valuation baseline
    to be measured against - it must not silently leak into period 0's
    calculation (this is also what the merge-pass optimization's
    "skip flows <= first boundary" step exists to preserve).
    """
    snapshots = [snap(10, 1000.0), snap(41, 1300.0)]
    # deposit dated BEFORE the first snapshot (day 10)
    transactions = [txn(0, TransactionType.DEPOSIT, amount=99999.0)]
    portfolio = make_portfolio(snapshots=snapshots, transactions=transactions, cash_balance=1300.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=41)).calculate(portfolio, [])

    # if the pre-history deposit leaked in, this would be wildly different
    assert result.twr_pct == pytest.approx(30.0, abs=1e-4)  # plain (1300-1000)/1000


def test_many_flows_across_many_periods_still_correctly_attributed():
    """Stress case for the merge-pass optimization: several periods, each
    with its own flow(s), confirms flow_idx advancing monotonically across
    periods doesn't skip or double-count anything.
    """
    snapshots = [snap(0, 1000.0), snap(10, 1100.0), snap(20, 1210.0), snap(30, 1431.0)]
    transactions = [
        txn(5, TransactionType.DEPOSIT, amount=100.0),   # in period 0->1
        txn(15, TransactionType.DEPOSIT, amount=100.0),  # in period 1->2
        txn(25, TransactionType.WITHDRAWAL, amount=50.0),  # in period 2->3
    ]
    portfolio = make_portfolio(snapshots=snapshots, transactions=transactions, cash_balance=1431.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=30)).calculate(portfolio, [])

    # period 0->1: (1100-100)/1000 - 1 = 0.0
    # period 1->2: (1210-100)/1100 - 1 = 0.00909...
    # period 2->3: (1431-(-50))/1210 - 1 = 0.2244...
    r1 = (1100 - 100) / 1000 - 1
    r2 = (1210 - 100) / 1100 - 1
    r3 = (1431 - (-50)) / 1210 - 1
    expected = ((1 + r1) * (1 + r2) * (1 + r3) - 1) * 100
    assert result.status == "ok"
    assert result.periods_used == 3
    assert result.twr_pct == pytest.approx(expected, abs=1e-4)


# --- CAGR (annualized_pct) — Milestone 7 -----------------------------------

def test_annualized_pct_matches_cumulative_for_exactly_one_year():
    """Over exactly 365 days, cumulative and annualized should be equal -
    the annualization exponent (365/elapsed_days) is exactly 1.
    """
    snapshots = [snap(0, 1000.0), snap(365, 1100.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1100.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=365)).calculate(portfolio, [])

    assert result.twr_pct == pytest.approx(10.0, abs=1e-4)
    assert result.annualized_pct == pytest.approx(10.0, abs=1e-4)


def test_annualized_pct_higher_than_cumulative_for_short_period():
    """A 10% cumulative gain over just 91 days (~1 quarter) compounds to a
    much higher annualized rate - (1.10)^4 - 1 = 46.41%, hand-verified.
    """
    snapshots = [snap(0, 1000.0), snap(91, 1100.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1100.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=91)).calculate(portfolio, [])

    expected_annualized = ((1.10) ** (365 / 91) - 1) * 100
    assert result.annualized_pct == pytest.approx(expected_annualized, abs=1e-2)
    assert result.annualized_pct > result.twr_pct


def test_annualized_pct_lower_than_cumulative_for_long_period():
    """A 50% cumulative gain over 3 years annualizes down to roughly 14.5%."""
    snapshots = [snap(0, 1000.0), snap(1095, 1500.0)]  # ~3 years
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1500.0)

    result = TwrCalculator(as_of=BASE + timedelta(days=1095)).calculate(portfolio, [])

    expected_annualized = ((1.50) ** (365 / 1095) - 1) * 100
    assert result.annualized_pct == pytest.approx(expected_annualized, abs=1e-2)
    assert result.annualized_pct < result.twr_pct


def test_annualized_pct_none_when_not_ok():
    portfolio = make_portfolio(snapshots=[])
    result = TwrCalculator(as_of=BASE).calculate(portfolio, [])
    assert result.status == "no_data"
    assert result.annualized_pct is None
