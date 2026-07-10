from datetime import datetime

import pytest

from engine.models import HoldingSnapshot, Portfolio, Snapshot

DT = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def make_holding_snapshot(**overrides):
    defaults = dict(symbol="AAPL", shares=10.0, market_value_base=1500.0)
    defaults.update(overrides)
    return HoldingSnapshot(**defaults)


def make_snapshot(**overrides):
    defaults = dict(
        id="snap-1",
        portfolio_id="demo",
        timestamp=DT,
        portfolio_value=2500.0,
        cash_balance=1000.0,
        invested=1000.0,
        base_currency="USD",
        holdings=[make_holding_snapshot()],
    )
    defaults.update(overrides)
    return Snapshot(**defaults)


# --- HoldingSnapshot validation ----------------------------------------------

def test_holding_snapshot_valid():
    h = make_holding_snapshot()
    assert h.symbol == "AAPL"


def test_holding_snapshot_requires_symbol():
    with pytest.raises(ValueError, match="symbol is required"):
        make_holding_snapshot(symbol="")


def test_holding_snapshot_rejects_negative_shares():
    with pytest.raises(ValueError, match="shares cannot be negative"):
        make_holding_snapshot(shares=-1)


def test_holding_snapshot_allows_zero_shares():
    # a fully-sold position that's still worth tracking historically
    h = make_holding_snapshot(shares=0, market_value_base=0)
    assert h.shares == 0


def test_holding_snapshot_rejects_negative_market_value():
    with pytest.raises(ValueError, match="market_value_base cannot be negative"):
        make_holding_snapshot(market_value_base=-1)


# --- Snapshot validation ------------------------------------------------------

def test_snapshot_valid():
    s = make_snapshot()
    assert s.id == "snap-1"
    assert len(s.holdings) == 1


def test_snapshot_requires_id():
    with pytest.raises(ValueError, match="id is required"):
        make_snapshot(id="")


def test_snapshot_requires_portfolio_id():
    with pytest.raises(ValueError, match="portfolio_id is required"):
        make_snapshot(portfolio_id="")


def test_snapshot_requires_datetime_timestamp():
    with pytest.raises(ValueError, match="timestamp must be a datetime"):
        make_snapshot(timestamp="2026-01-01")  # a string, not a datetime


def test_snapshot_rejects_negative_portfolio_value():
    with pytest.raises(ValueError, match="portfolio_value cannot be negative"):
        make_snapshot(portfolio_value=-1)


def test_snapshot_rejects_negative_cash_balance():
    with pytest.raises(ValueError, match="cash_balance cannot be negative"):
        make_snapshot(cash_balance=-1)


def test_snapshot_rejects_negative_invested():
    with pytest.raises(ValueError, match="invested cannot be negative"):
        make_snapshot(invested=-1)


def test_snapshot_requires_base_currency():
    with pytest.raises(ValueError, match="base_currency is required"):
        make_snapshot(base_currency="")


def test_snapshot_defaults_holdings_to_empty():
    s = Snapshot(
        id="s1",
        portfolio_id="demo",
        timestamp=DT,
        portfolio_value=0.0,
        cash_balance=0.0,
        invested=0.0,
        base_currency="USD",
    )
    assert s.holdings == []


# --- Serialization -------------------------------------------------------------

def test_holding_snapshot_round_trips_through_dict():
    original = make_holding_snapshot()
    restored = HoldingSnapshot.from_dict(original.to_dict())
    assert restored == original


def test_snapshot_round_trips_through_dict():
    original = make_snapshot()
    restored = Snapshot.from_dict(original.to_dict())
    assert restored == original


def test_snapshot_to_dict_timestamp_is_json_safe_string():
    s = make_snapshot()
    d = s.to_dict()
    assert isinstance(d["timestamp"], str)
    assert d["timestamp"] == DT.isoformat()


def test_snapshot_from_dict_accepts_z_suffix_timestamp():
    """Same portability concern as YamlRepository's transaction parsing -
    datetime.fromisoformat's "Z" support varies by Python version, so this
    is normalized explicitly rather than relying on stdlib behavior alone.
    """
    data = make_snapshot().to_dict()
    data["timestamp"] = "2026-01-01T00:00:00Z"
    restored = Snapshot.from_dict(data)
    assert restored.timestamp == DT


def test_snapshot_from_dict_missing_holdings_key_defaults_to_empty():
    """Migration safety: an older-schema snapshot dict (or one written by
    a hypothetical future minimal writer) without a `holdings` key at all
    should still load, not raise a KeyError.
    """
    data = make_snapshot().to_dict()
    del data["holdings"]
    restored = Snapshot.from_dict(data)
    assert restored.holdings == []


def test_snapshot_to_dict_holdings_are_plain_dicts_not_dataclasses():
    d = make_snapshot().to_dict()
    assert isinstance(d["holdings"], list)
    assert isinstance(d["holdings"][0], dict)
    assert d["holdings"][0]["symbol"] == "AAPL"


# --- Portfolio.snapshots (additive field) -------------------------------------

def test_portfolio_defaults_snapshots_to_empty_list():
    p = Portfolio(id="p1", name="Test")
    assert p.snapshots == []


def test_portfolio_accepts_snapshots():
    snap = make_snapshot()
    p = Portfolio(id="p1", name="Test", snapshots=[snap])
    assert p.snapshots == [snap]


def test_pre_milestone_6_portfolio_construction_still_works():
    """The exact backward-compatibility bar every prior milestone was held to."""
    p = Portfolio(id="p1", name="Test", base_currency="USD", cash_balance=500.0)
    assert p.snapshots == []
    assert p.transactions == []
