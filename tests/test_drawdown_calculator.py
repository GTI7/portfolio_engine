from datetime import datetime, timedelta

import pytest

from engine.calculators.drawdown_calculator import DrawdownCalculator
from engine.models import Portfolio, Snapshot

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


def make_portfolio(snapshots=None, cash_balance=0.0):
    return Portfolio(id="demo", name="Demo", cash_balance=cash_balance, snapshots=snapshots or [])


def test_no_snapshots_is_no_data():
    result = DrawdownCalculator(as_of=BASE).calculate(make_portfolio(), [])
    assert result.status == "no_data"


def test_single_snapshot_is_trivially_at_peak():
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0)], cash_balance=1000.0)
    result = DrawdownCalculator(as_of=BASE).calculate(portfolio, [])

    assert result.status == "ok"
    assert result.current_drawdown_pct == 0.0
    assert result.maximum_drawdown_pct == 0.0
    assert result.recovery_status == "at_peak"


def test_monotonic_rise_has_zero_drawdown():
    snapshots = [snap(0, 1000.0), snap(10, 1100.0), snap(20, 1200.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1200.0)
    result = DrawdownCalculator(as_of=BASE + timedelta(days=20)).calculate(portfolio, [])

    assert result.current_drawdown_pct == 0.0
    assert result.maximum_drawdown_pct == 0.0
    assert result.peak_value == 1200.0
    assert result.recovery_status == "at_peak"


def test_simple_drawdown_from_peak():
    snapshots = [snap(0, 1000.0), snap(10, 1200.0), snap(20, 900.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=900.0)
    result = DrawdownCalculator(as_of=BASE + timedelta(days=20)).calculate(portfolio, [])

    # peak=1200, current=900 -> (900-1200)/1200 = -25%
    assert result.current_drawdown_pct == pytest.approx(-25.0, abs=1e-4)
    assert result.maximum_drawdown_pct == pytest.approx(-25.0, abs=1e-4)
    assert result.peak_value == 1200.0
    assert result.recovery_status == "in_drawdown"


def test_recovering_status_when_above_max_drawdown_but_not_at_peak():
    # peak 1200, fell to 900 (-25%), recovered partway to 1000 (-16.67%)
    snapshots = [snap(0, 1000.0), snap(10, 1200.0), snap(20, 900.0), snap(30, 1000.0)]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1000.0)
    result = DrawdownCalculator(as_of=BASE + timedelta(days=30)).calculate(portfolio, [])

    assert result.maximum_drawdown_pct == pytest.approx(-25.0, abs=1e-4)
    assert result.current_drawdown_pct == pytest.approx((1000 - 1200) / 1200 * 100, abs=1e-4)
    assert result.recovery_status == "recovering"


def test_max_drawdown_persists_after_recovery_to_new_peak():
    snapshots = [
        snap(0, 1000.0),
        snap(10, 1200.0),   # peak 1
        snap(20, 900.0),    # -25% drawdown
        snap(30, 1300.0),   # new peak, fully recovered
    ]
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=1300.0)
    result = DrawdownCalculator(as_of=BASE + timedelta(days=30)).calculate(portfolio, [])

    assert result.current_drawdown_pct == 0.0
    assert result.maximum_drawdown_pct == pytest.approx(-25.0, abs=1e-4)  # historical max persists
    assert result.peak_value == 1300.0
    assert result.recovery_status == "at_peak"


def test_uses_current_value_as_synthetic_final_point():
    snapshots = [snap(0, 1000.0), snap(10, 1200.0)]
    # cash_balance implies current value dropped to 600 since last snapshot
    portfolio = make_portfolio(snapshots=snapshots, cash_balance=600.0)
    result = DrawdownCalculator(as_of=BASE + timedelta(days=20)).calculate(portfolio, [])

    assert result.current_drawdown_pct == pytest.approx((600 - 1200) / 1200 * 100, abs=1e-4)


def test_default_as_of_uses_current_time_when_not_injected():
    portfolio = make_portfolio(snapshots=[snap(0, 1000.0)], cash_balance=1000.0)
    result = DrawdownCalculator().calculate(portfolio, [])
    assert result.as_of is not None
