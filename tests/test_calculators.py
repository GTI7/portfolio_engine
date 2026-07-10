from engine.calculators.allocation_calculator import AllocationCalculator
from engine.calculators.performance_calculator import PerformanceCalculator
from engine.calculators.portfolio_calculator import PortfolioCalculator
from engine.models import Holding, Portfolio, Position, Quote


def make_position(symbol, shares, avg_price, price, currency="USD", type_="stock", change_pct=0.0):
    holding = Holding(
        symbol=symbol, shares=shares, avg_price=avg_price, currency=currency, type=type_
    )
    quote = Quote(symbol=symbol, price=price, currency=currency, change_pct=change_pct)
    market_value = price * shares
    cost_basis = avg_price * shares
    gain = market_value - cost_basis
    return Position(
        holding=holding,
        quote=quote,
        market_value=round(market_value, 2),
        market_value_base=round(market_value, 2),
        cost_basis=round(cost_basis, 2),
        cost_basis_base=round(cost_basis, 2),
        unrealized_gain=round(gain, 2),
        gain_pct=round((gain / cost_basis * 100) if cost_basis else 0, 2),
        day_change_pct=change_pct,
        fx_rate=1.0,
    )


def make_portfolio(cash_balance=0.0, base_currency="USD"):
    return Portfolio(id="test", name="Test", base_currency=base_currency, cash_balance=cash_balance)


def test_portfolio_calculator_basic():
    positions = [
        make_position("AAPL", 10, 100, 150),   # +500
        make_position("MSFT", 5, 200, 180),    # -100
    ]
    result = PortfolioCalculator().calculate(make_portfolio(), positions)
    assert result.total_positions_value == 10 * 150 + 5 * 180
    assert result.total_invested == 10 * 100 + 5 * 200
    assert result.total_unrealized_gain == 400
    assert result.roi_pct == round(400 / 2000 * 100, 2)
    assert result.cash_balance == 0.0
    assert result.total_value == result.total_positions_value


def test_portfolio_calculator_includes_cash_in_total_value_not_roi():
    positions = [make_position("AAPL", 10, 100, 150)]  # value 1500, invested 1000, +500
    result = PortfolioCalculator().calculate(make_portfolio(cash_balance=2000), positions)
    assert result.total_positions_value == 1500
    assert result.cash_balance == 2000
    assert result.total_value == 3500  # positions + cash
    assert result.total_invested == 1000  # cash never counted as "invested"
    assert result.roi_pct == 50.0  # unaffected by cash


def test_portfolio_calculator_handles_zero_invested():
    result = PortfolioCalculator().calculate(make_portfolio(), [])
    assert result.total_invested == 0
    assert result.roi_pct == 0.0
    assert result.total_value == 0.0


def test_portfolio_calculator_cash_only_portfolio():
    result = PortfolioCalculator().calculate(make_portfolio(cash_balance=1000), [])
    assert result.total_value == 1000
    assert result.total_positions_value == 0
    assert result.roi_pct == 0.0  # no invested capital, not a divide-by-zero error


def test_allocation_calculator_groups_by_type():
    positions = [
        make_position("AAPL", 10, 100, 150, type_="stock"),
        make_position("VWCE", 10, 100, 100, type_="etf"),
        make_position("BTC", 1, 30000, 40000, type_="crypto"),
    ]
    groups = AllocationCalculator(group_by="type").calculate(make_portfolio(), positions)
    labels = {g.label for g in groups}
    assert labels == {"stock", "etf", "crypto"}
    total_pct = round(sum(g.pct for g in groups))
    assert total_pct == 100


def test_allocation_calculator_includes_cash_group_and_sums_to_100():
    positions = [make_position("AAPL", 10, 100, 150, type_="stock")]  # value 1500
    groups = AllocationCalculator(group_by="type").calculate(
        make_portfolio(cash_balance=500), positions
    )
    labels = {g.label: g for g in groups}
    assert "Cash" in labels
    assert labels["Cash"].value == 500
    assert round(sum(g.pct for g in groups)) == 100
    # 1500 stock / 2000 total = 75%, 500 cash / 2000 total = 25%
    assert labels["Cash"].pct == 25.0


def test_allocation_calculator_omits_cash_group_when_zero():
    positions = [make_position("AAPL", 10, 100, 150, type_="stock")]
    groups = AllocationCalculator(group_by="type").calculate(
        make_portfolio(cash_balance=0), positions
    )
    assert "Cash" not in {g.label for g in groups}


def test_allocation_calculator_empty_portfolio():
    groups = AllocationCalculator().calculate(make_portfolio(), [])
    assert groups == []


def test_performance_calculator_weighted_average():
    positions = [
        make_position("AAPL", 10, 100, 150, change_pct=2.0),   # value 1500
        make_position("MSFT", 10, 100, 50, change_pct=-4.0),   # value 500
    ]
    # weighted: 1500/2000*2.0 + 500/2000*-4.0 = 1.5 - 1.0 = 0.5
    result = PerformanceCalculator().calculate(make_portfolio(), positions)
    assert result.day_change_pct == 0.5
    assert result.weekly_change_pct == 0.0  # stubbed per ADR-0003


def test_performance_calculator_cash_dilutes_weighted_change():
    positions = [make_position("AAPL", 10, 100, 150, change_pct=2.0)]  # value 1500
    # 1500 moving +2%, plus 1500 cash moving 0% -> total 3000, weighted change = 1500/3000*2.0 = 1.0
    result = PerformanceCalculator().calculate(make_portfolio(cash_balance=1500), positions)
    assert result.day_change_pct == 1.0


def test_performance_calculator_empty_portfolio():
    result = PerformanceCalculator().calculate(make_portfolio(), [])
    assert result.day_change_pct == 0.0


def make_converted_position(
    symbol, shares, avg_price, price, currency, fx_rate, change_pct=0.0
):
    """Like make_position, but simulates a holding in a foreign currency
    already converted by PortfolioEngine.build_positions - this is what a
    real multi-currency Position looks like by the time a calculator sees
    it (calculators never do FX conversion themselves).
    """
    holding = Holding(
        symbol=symbol, shares=shares, avg_price=avg_price, currency=currency, type="stock"
    )
    quote = Quote(symbol=symbol, price=price, currency=currency, change_pct=change_pct)
    market_value = price * shares
    cost_basis = avg_price * shares
    market_value_base = market_value * fx_rate
    cost_basis_base = cost_basis * fx_rate
    gain = market_value_base - cost_basis_base
    return Position(
        holding=holding,
        quote=quote,
        market_value=round(market_value, 2),
        market_value_base=round(market_value_base, 2),
        cost_basis=round(cost_basis, 2),
        cost_basis_base=round(cost_basis_base, 2),
        unrealized_gain=round(gain, 2),
        gain_pct=round((gain / cost_basis_base * 100) if cost_basis_base else 0, 2),
        day_change_pct=change_pct,
        fx_rate=fx_rate,
    )


def test_portfolio_calculator_sums_across_currencies_using_base_currency_figures():
    positions = [
        make_position("AAPL", 10, 100, 150, currency="USD"),  # USD==base: value 1500, cost 1000
        make_converted_position(
            "VOD.L", 100, 2.0, 2.5, currency="GBP", fx_rate=1.17
        ),  # GBP->EUR: value 250*1.17=292.5, cost 200*1.17=234
    ]
    result = PortfolioCalculator().calculate(make_portfolio(base_currency="EUR"), positions)
    assert result.total_positions_value == round(1500 + 292.5, 2)
    assert result.total_invested == round(1000 + 234, 2)


def test_allocation_calculator_groups_across_currencies_by_base_value():
    positions = [
        make_position("AAPL", 10, 100, 150, type_="stock", currency="USD"),  # 1500
        make_converted_position("VOD.L", 100, 2.0, 2.5, currency="GBP", fx_rate=1.17),  # 292.5
    ]
    groups = AllocationCalculator(group_by="type").calculate(
        make_portfolio(base_currency="EUR"), positions
    )
    # both positions are type="stock" (default in make_converted_position),
    # so they should combine into one group using base-currency values
    assert len(groups) == 1
    assert groups[0].value == round(1500 + 292.5, 2)
