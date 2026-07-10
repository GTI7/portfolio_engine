import pytest

from engine.models import Holding, Portfolio


def test_holding_valid():
    h = Holding(symbol="AAPL", shares=10, avg_price=150.0, currency="USD", type="stock")
    assert h.symbol == "AAPL"


def test_holding_rejects_negative_shares():
    with pytest.raises(ValueError):
        Holding(symbol="AAPL", shares=-1, avg_price=150.0, currency="USD", type="stock")


def test_holding_rejects_negative_price():
    with pytest.raises(ValueError):
        Holding(symbol="AAPL", shares=10, avg_price=-1.0, currency="USD", type="stock")


def test_holding_requires_currency():
    with pytest.raises(ValueError):
        Holding(symbol="AAPL", shares=10, avg_price=150.0, currency="", type="stock")


def test_holding_requires_type():
    with pytest.raises(ValueError):
        Holding(symbol="AAPL", shares=10, avg_price=150.0, currency="USD", type="")


def test_portfolio_defaults_cash_to_zero():
    p = Portfolio(id="p1", name="Test")
    assert p.cash_balance == 0.0


def test_portfolio_accepts_positive_cash_balance():
    p = Portfolio(id="p1", name="Test", cash_balance=1500.0)
    assert p.cash_balance == 1500.0


def test_portfolio_rejects_negative_cash_balance():
    with pytest.raises(ValueError):
        Portfolio(id="p1", name="Test", cash_balance=-1.0)
