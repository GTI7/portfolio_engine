
from engine.calculators.allocation_calculator import AllocationCalculator
from engine.calculators.performance_calculator import PerformanceCalculator
from engine.calculators.portfolio_calculator import PortfolioCalculator
from engine.models import Holding, Portfolio, Quote
from engine.portfolio_engine import PortfolioEngine


def build_engine() -> PortfolioEngine:
    return PortfolioEngine(
        {
            "summary": PortfolioCalculator(),
            "allocation": AllocationCalculator(group_by="type"),
            "performance": PerformanceCalculator(),
        }
    )


def test_end_to_end_run():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        holdings=[
            Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock"),
            Holding(symbol="MSFT", shares=5, avg_price=200, currency="USD", type="stock"),
        ],
    )
    quotes = {
        "AAPL": Quote(symbol="AAPL", price=150, currency="USD", change_pct=1.0),
        "MSFT": Quote(symbol="MSFT", price=180, currency="USD", change_pct=-0.5),
    }

    result = build_engine().run(portfolio, quotes)

    assert "positions" in result
    assert len(result["positions"]) == 2
    assert result["summary"].total_value == 10 * 150 + 5 * 180
    assert result["allocation"][0].label == "stock"
    assert result["allocation"][0].pct == 100.0
    assert isinstance(result["performance"].day_change_pct, float)


def test_missing_quote_defaults_to_zero_price():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        holdings=[Holding(symbol="GHOST", shares=10, avg_price=100, currency="USD", type="stock")],
    )
    result = build_engine().run(portfolio, quotes={})
    position = result["positions"][0]
    assert position.market_value == 0
    assert position.unrealized_gain == -1000  # lost the full cost basis in this degraded case


def test_cash_flows_through_full_engine_run():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        cash_balance=1000.0,
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock")],
    )
    quotes = {"AAPL": Quote(symbol="AAPL", price=150, currency="USD", change_pct=2.0)}

    result = build_engine().run(portfolio, quotes)

    assert result["summary"].cash_balance == 1000.0
    assert result["summary"].total_value == 1500 + 1000  # positions + cash
    assert result["summary"].total_invested == 1000  # cash excluded from invested capital
    cash_group = next(g for g in result["allocation"] if g.label == "Cash")
    assert cash_group.value == 1000.0


def test_multi_currency_conversion_flows_through_full_engine_run():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="EUR",
        holdings=[
            Holding(symbol="MC.PA", shares=5, avg_price=600.0, currency="EUR", type="stock"),
            Holding(symbol="AAPL", shares=10, avg_price=150.0, currency="USD", type="stock"),
        ],
    )
    quotes = {
        "MC.PA": Quote(symbol="MC.PA", price=650.0, currency="EUR", change_pct=1.0),
        "AAPL": Quote(symbol="AAPL", price=200.0, currency="USD", change_pct=2.0),
    }
    # 1 USD = 0.92 EUR
    fx_rates = {"USD": 0.92}

    result = build_engine().run(portfolio, quotes, fx_rates)

    positions = {p.symbol: p for p in result["positions"]}
    assert positions["MC.PA"].fx_rate == 1.0  # already base currency
    assert positions["MC.PA"].market_value_base == 5 * 650.0
    assert positions["AAPL"].fx_rate == 0.92
    assert positions["AAPL"].market_value_base == round(10 * 200.0 * 0.92, 2)
    assert positions["AAPL"].cost_basis_base == round(10 * 150.0 * 0.92, 2)

    expected_total_value = (5 * 650.0) + round(10 * 200.0 * 0.92, 2)
    assert result["summary"].total_positions_value == round(expected_total_value, 2)


def test_missing_fx_rate_falls_back_to_1_0_not_a_crash():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="EUR",
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock")],
    )
    quotes = {"AAPL": Quote(symbol="AAPL", price=150, currency="USD")}

    # fx_rates omitted entirely - USD position falls back to a 1.0 rate
    # (documented best-effort, not a crash; the caller layer is responsible
    # for surfacing that a rate was missing - see update_logic.py)
    result = build_engine().run(portfolio, quotes, fx_rates=None)
    position = result["positions"][0]
    assert position.fx_rate == 1.0
    assert position.market_value_base == 1500.0


def test_engine_with_all_five_calculators_including_milestone_4():
    from datetime import datetime

    from engine.calculators.reconciliation_calculator import ReconciliationCalculator
    from engine.calculators.transaction_calculator import TransactionCalculator
    from engine.models import Transaction, TransactionType

    engine = PortfolioEngine(
        {
            "summary": PortfolioCalculator(),
            "allocation": AllocationCalculator(group_by="type"),
            "performance": PerformanceCalculator(),
            "reconciliation": ReconciliationCalculator(),
            "transactions": TransactionCalculator(),
        }
    )
    transactions = [
        Transaction(
            id="t0",
            portfolio_id="demo",
            type=TransactionType.DEPOSIT,
            date=datetime.fromisoformat("2025-12-31T00:00:00+00:00"),
            currency="USD",
            amount=1000.0,
        ),
        Transaction(
            id="t1",
            portfolio_id="demo",
            type=TransactionType.BUY,
            date=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            currency="USD",
            amount=1000.0,
            symbol="AAPL",
            shares=10,
            price=100.0,
        ),
    ]
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock")],
        transactions=transactions,
    )
    quotes = {"AAPL": Quote(symbol="AAPL", price=150, currency="USD")}

    result = engine.run(portfolio, quotes)

    assert result["reconciliation"].status == "ok"
    assert result["transactions"].count == 2
    # existing calculators still work unaffected by the two new ones
    assert result["summary"].total_positions_value == 1500.0
