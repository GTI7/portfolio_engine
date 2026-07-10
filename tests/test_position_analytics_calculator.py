import pytest

from engine.calculators.position_analytics_calculator import PositionAnalyticsCalculator
from engine.models import Holding, Portfolio, Position, Quote


def make_position(symbol, market_value, gain_pct):
    holding = Holding(symbol=symbol, shares=1, avg_price=1, currency="USD", type="stock")
    quote = Quote(symbol=symbol, price=1, currency="USD")
    return Position(
        holding=holding,
        quote=quote,
        market_value=market_value,
        market_value_base=market_value,
        cost_basis=market_value,
        cost_basis_base=market_value,
        unrealized_gain=0.0,
        gain_pct=gain_pct,
        day_change_pct=0.0,
    )


def make_portfolio():
    return Portfolio(id="demo", name="Demo")


def test_no_positions_is_no_data():
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), [])
    assert result.status == "no_data"
    assert result.holding_count == 0


def test_single_position_is_fully_concentrated():
    positions = [make_position("AAPL", 1000.0, 10.0)]
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), positions)

    assert result.status == "ok"
    assert result.largest_position.symbol == "AAPL"
    assert result.largest_position.pct_of_portfolio == 100.0
    assert result.herfindahl_index == pytest.approx(1.0, abs=1e-6)
    assert result.diversification_score == pytest.approx(0.0, abs=1e-2)


def test_two_equal_positions_are_evenly_diversified():
    positions = [make_position("AAPL", 500.0, 0.0), make_position("MSFT", 500.0, 0.0)]
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), positions)

    assert result.largest_position.pct_of_portfolio == 50.0
    # HHI for two equal 50% weights = 0.25+0.25 = 0.5
    assert result.herfindahl_index == pytest.approx(0.5, abs=1e-6)
    assert result.diversification_score == pytest.approx(50.0, abs=1e-2)


def test_largest_winner_and_loser():
    positions = [
        make_position("AAPL", 300.0, 25.0),   # winner
        make_position("MSFT", 300.0, -15.0),  # loser
        make_position("GOOG", 400.0, 5.0),
    ]
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), positions)

    assert result.largest_winner.symbol == "AAPL"
    assert result.largest_winner.gain_pct == 25.0
    assert result.largest_loser.symbol == "MSFT"
    assert result.largest_loser.gain_pct == -15.0


def test_top5_concentration_with_more_than_five_positions():
    positions = [make_position(f"SYM{i}", 100.0, 0.0) for i in range(8)]  # 8 equal positions
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), positions)

    # each position is 100/800 = 12.5%, top 5 = 62.5%
    assert result.top5_concentration_pct == pytest.approx(62.5, abs=1e-4)
    assert result.holding_count == 8


def test_top5_concentration_with_fewer_than_five_positions():
    positions = [make_position("AAPL", 600.0, 0.0), make_position("MSFT", 400.0, 0.0)]
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), positions)

    # with only 2 positions, top5 concentration = 100% (everything)
    assert result.top5_concentration_pct == pytest.approx(100.0, abs=1e-4)


def test_herfindahl_index_hand_verified():
    # weights: 0.5, 0.3, 0.2 -> HHI = 0.25 + 0.09 + 0.04 = 0.38
    positions = [
        make_position("A", 500.0, 0.0),
        make_position("B", 300.0, 0.0),
        make_position("C", 200.0, 0.0),
    ]
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), positions)

    assert result.herfindahl_index == pytest.approx(0.38, abs=1e-4)
    assert result.diversification_score == pytest.approx(62.0, abs=1e-2)


def test_zero_total_value_is_no_data():
    positions = [make_position("AAPL", 0.0, 0.0)]
    result = PositionAnalyticsCalculator().calculate(make_portfolio(), positions)
    assert result.status == "no_data"
    assert result.holding_count == 1
