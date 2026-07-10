from datetime import datetime, timedelta

from engine.calculators.portfolio_calculator import PortfolioCalculator
from engine.models import Holding, Portfolio, Position, Quote, Snapshot
from engine.snapshot_policy import build_snapshot, should_create_snapshot

BASE = datetime.fromisoformat("2026-01-01T08:00:00+00:00")


def make_snapshot(offset_days=0, **overrides):
    defaults = dict(
        id=f"snap-{offset_days}",
        portfolio_id="demo",
        timestamp=BASE + timedelta(days=offset_days),
        portfolio_value=1000.0,
        cash_balance=100.0,
        invested=900.0,
        base_currency="USD",
    )
    defaults.update(overrides)
    return Snapshot(**defaults)


# --- should_create_snapshot: first snapshot -------------------------------------

def test_first_snapshot_is_created_when_none_exist():
    assert should_create_snapshot([], now=BASE) is True


# --- should_create_snapshot: duplicate prevention --------------------------------

def test_no_second_snapshot_same_calendar_date():
    existing = [make_snapshot(offset_days=0)]
    later_same_day = BASE + timedelta(hours=6)  # same date, different time
    assert should_create_snapshot(existing, now=later_same_day) is False


def test_snapshot_created_on_a_new_calendar_date():
    existing = [make_snapshot(offset_days=0)]
    next_day = BASE + timedelta(days=1)
    assert should_create_snapshot(existing, now=next_day) is True


def test_only_todays_snapshot_blocks_not_any_snapshot_ever():
    existing = [make_snapshot(offset_days=0), make_snapshot(offset_days=1)]
    two_days_later = BASE + timedelta(days=2)
    assert should_create_snapshot(existing, now=two_days_later) is True


def test_gap_in_history_does_not_confuse_the_check():
    """Missing days in between (e.g. HA was off) shouldn't affect whether
    today specifically already has a snapshot.
    """
    existing = [make_snapshot(offset_days=0), make_snapshot(offset_days=10)]
    assert should_create_snapshot(existing, now=BASE + timedelta(days=10, hours=3)) is False
    assert should_create_snapshot(existing, now=BASE + timedelta(days=11)) is True


# --- build_snapshot ---------------------------------------------------------------

def _make_position(symbol, shares, price):
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


def test_build_snapshot_captures_current_state():
    portfolio = Portfolio(id="demo", name="Demo", base_currency="USD", cash_balance=500.0)
    positions = [_make_position("AAPL", 10, 150.0)]
    summary = PortfolioCalculator().calculate(portfolio, positions)

    snap = build_snapshot(portfolio, summary, positions, timestamp=BASE)

    assert snap.portfolio_id == "demo"
    assert snap.timestamp == BASE
    assert snap.base_currency == "USD"
    assert snap.portfolio_value == summary.total_value
    assert snap.cash_balance == summary.cash_balance
    assert snap.invested == summary.total_invested
    assert len(snap.holdings) == 1
    assert snap.holdings[0].symbol == "AAPL"
    assert snap.holdings[0].shares == 10
    assert snap.holdings[0].market_value_base == 1500.0


def test_build_snapshot_generates_a_fresh_id_each_call():
    portfolio = Portfolio(id="demo", name="Demo")
    summary = PortfolioCalculator().calculate(portfolio, [])

    snap1 = build_snapshot(portfolio, summary, [], timestamp=BASE)
    snap2 = build_snapshot(portfolio, summary, [], timestamp=BASE)

    assert snap1.id != snap2.id  # each call is a distinct, identifiable event


def test_build_snapshot_with_no_positions():
    portfolio = Portfolio(id="demo", name="Demo", cash_balance=1000.0)
    summary = PortfolioCalculator().calculate(portfolio, [])

    snap = build_snapshot(portfolio, summary, [], timestamp=BASE)

    assert snap.holdings == []
    assert snap.portfolio_value == 1000.0
