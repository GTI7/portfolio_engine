from datetime import datetime, timedelta

from custom_components.portfolio_engine import sensor_mapping
from custom_components.portfolio_engine.engine.calculators.allocation_calculator import (
    AllocationCalculator,
)
from custom_components.portfolio_engine.engine.calculators.dividend_calculator import (
    DividendCalculator,
)
from custom_components.portfolio_engine.engine.calculators.drawdown_calculator import (
    DrawdownCalculator,
)
from custom_components.portfolio_engine.engine.calculators.mwr_calculator import MwrCalculator
from custom_components.portfolio_engine.engine.calculators.performance_calculator import (
    PerformanceCalculator,
)
from custom_components.portfolio_engine.engine.calculators.portfolio_calculator import (
    PortfolioCalculator,
)
from custom_components.portfolio_engine.engine.calculators.position_analytics_calculator import (
    PositionAnalyticsCalculator,
)
from custom_components.portfolio_engine.engine.calculators.reconciliation_calculator import (
    ReconciliationCalculator,
)
from custom_components.portfolio_engine.engine.calculators.transaction_calculator import (
    TransactionCalculator,
)
from custom_components.portfolio_engine.engine.calculators.twr_calculator import TwrCalculator
from custom_components.portfolio_engine.engine.calculators.volatility_calculator import (
    VolatilityCalculator,
)
from custom_components.portfolio_engine.engine.models import (
    Holding,
    Portfolio,
    Quote,
    Transaction,
    TransactionType,
)
from custom_components.portfolio_engine.engine.portfolio_engine import PortfolioEngine

AS_OF = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def build_sample_data(transactions=None, snapshots=None):
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        cash_balance=1000.0,
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock")],
        transactions=transactions or [],
        snapshots=snapshots or [],
    )
    quotes = {"AAPL": Quote(symbol="AAPL", price=150, currency="USD", change_pct=2.0)}
    engine = PortfolioEngine(
        {
            "summary": PortfolioCalculator(),
            "allocation": AllocationCalculator(group_by="type"),
            "performance": PerformanceCalculator(),
            "reconciliation": ReconciliationCalculator(),
            "transactions": TransactionCalculator(),
            "mwr": MwrCalculator(as_of=AS_OF),
            "twr": TwrCalculator(as_of=AS_OF),
            "dividends": DividendCalculator(as_of=AS_OF),
            "drawdown": DrawdownCalculator(as_of=AS_OF),
            "volatility": VolatilityCalculator(as_of=AS_OF),
            "concentration": PositionAnalyticsCalculator(),
        }
    )
    data = engine.run(portfolio, quotes)
    data["portfolio_id"] = portfolio.id
    data["portfolio_name"] = portfolio.name
    data["base_currency"] = portfolio.base_currency
    data["symbols_missing_quotes"] = []
    data["fx_rates_missing"] = []
    return data


def test_get_portfolio_value_includes_cash():
    data = build_sample_data()
    # 10 shares * 150 = 1500 positions value + 1000 cash = 2500
    assert sensor_mapping.get_portfolio_value(data) == 2500.0


def test_get_total_invested_excludes_cash():
    data = build_sample_data()
    assert sensor_mapping.get_total_invested(data) == 1000.0  # 10 * 100 avg_price


def test_get_cash_balance():
    data = build_sample_data()
    assert sensor_mapping.get_cash_balance(data) == 1000.0


def test_get_roi_unaffected_by_cash():
    data = build_sample_data()
    assert sensor_mapping.get_roi(data) == 50.0  # (1500-1000)/1000 * 100


def test_get_positions_count():
    data = build_sample_data()
    assert sensor_mapping.get_positions_count(data) == 1


def test_get_positions_attributes_shape():
    data = build_sample_data()
    attrs = sensor_mapping.get_positions_attributes(data)
    assert attrs["portfolio_id"] == "demo"
    assert attrs["base_currency"] == "USD"
    assert len(attrs["positions"]) == 1
    position = attrs["positions"][0]
    assert position["holding"]["symbol"] == "AAPL"
    assert position["market_value"] == 1500.0
    # quote's as_of should be JSON-safe (isoformat string or None), not a
    # raw datetime object
    assert not hasattr(position["quote"].get("as_of"), "isoformat") or position["quote"][
        "as_of"
    ] is None or isinstance(position["quote"]["as_of"], str)


# --- Milestone 4: transaction_count / reconciliation mapping functions -------

def make_transaction(offset_id, type_=TransactionType.DEPOSIT, **kwargs):
    defaults = dict(
        id=f"txn-{offset_id}",
        portfolio_id="demo",
        type=type_,
        date=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        currency="USD",
        amount=100.0,
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def test_get_transaction_count_empty_log():
    data = build_sample_data(transactions=[])
    assert sensor_mapping.get_transaction_count(data) == 0


def test_get_transaction_count_and_attributes():
    transactions = [make_transaction(0), make_transaction(1)]
    data = build_sample_data(transactions=transactions)

    assert sensor_mapping.get_transaction_count(data) == 2
    attrs = sensor_mapping.get_transaction_attributes(data)
    assert len(attrs["recent"]) == 2
    # date/type must be JSON-safe (strings), not raw datetime/enum objects
    assert isinstance(attrs["recent"][0]["date"], str)
    assert isinstance(attrs["recent"][0]["type"], str)
    assert attrs["recent"][0]["type"] == "deposit"


def test_get_reconciliation_status_no_data():
    data = build_sample_data(transactions=[])
    assert sensor_mapping.get_reconciliation_status(data) == "no_data"
    attrs = sensor_mapping.get_reconciliation_attributes(data)
    assert attrs["discrepancies"] == []
    assert attrs["transactions_considered"] == 0


def test_get_reconciliation_status_ok():
    # matches the sample portfolio exactly: 10 shares @ 100, cash 1000
    transactions = [
        make_transaction(0, TransactionType.DEPOSIT, amount=2000.0),
        make_transaction(
            1, TransactionType.BUY, symbol="AAPL", shares=10, price=100.0, amount=1000.0
        ),
    ]
    data = build_sample_data(transactions=transactions)

    assert sensor_mapping.get_reconciliation_status(data) == "ok"
    attrs = sensor_mapping.get_reconciliation_attributes(data)
    assert attrs["discrepancies"] == []
    assert attrs["transactions_considered"] == 2


def test_get_reconciliation_status_discrepancy_with_attribute_shape():
    # declared holding is 10 shares @ 100, but log only shows a 5-share buy
    transactions = [
        make_transaction(0, TransactionType.DEPOSIT, amount=2000.0),
        make_transaction(
            1, TransactionType.BUY, symbol="AAPL", shares=5, price=100.0, amount=500.0
        ),
    ]
    data = build_sample_data(transactions=transactions)

    assert sensor_mapping.get_reconciliation_status(data) == "discrepancy"
    attrs = sensor_mapping.get_reconciliation_attributes(data)
    assert len(attrs["discrepancies"]) >= 1
    discrepancy = attrs["discrepancies"][0]
    assert set(discrepancy.keys()) == {"symbol", "field", "declared", "reconstructed", "difference"}


# --- Milestone 5: money-weighted return mapping functions --------------------

def test_get_mwr_none_when_no_data():
    data = build_sample_data(transactions=[])
    assert sensor_mapping.get_mwr(data) is None
    attrs = sensor_mapping.get_mwr_attributes(data)
    assert attrs["status"] == "no_data"
    assert attrs["cash_flow_count"] == 0


def test_get_mwr_returns_percentage_when_ok():
    transactions = [
        Transaction(
            id="t1",
            portfolio_id="demo",
            type=TransactionType.DEPOSIT,
            date=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
            currency="USD",
            amount=2000.0,
        )
    ]
    # matches the sample portfolio: 10 shares @ 150 = 1500 + 1000 cash = 2500 terminal
    data = build_sample_data(transactions=transactions)

    assert sensor_mapping.get_mwr(data) is not None
    assert isinstance(sensor_mapping.get_mwr(data), float)
    attrs = sensor_mapping.get_mwr_attributes(data)
    assert attrs["status"] == "ok"
    assert attrs["cash_flow_count"] == 2
    assert attrs["as_of"] == AS_OF.isoformat()


def test_get_mwr_none_when_not_ok_status():
    # a single deposit dated exactly at AS_OF - no time spread -> insufficient_data
    transactions = [
        Transaction(
            id="t1",
            portfolio_id="demo",
            type=TransactionType.DEPOSIT,
            date=AS_OF,
            currency="USD",
            amount=1000.0,
        )
    ]
    data = build_sample_data(transactions=transactions)

    assert sensor_mapping.get_mwr(data) is None
    assert sensor_mapping.get_mwr_attributes(data)["status"] == "insufficient_data"


# --- Milestone 6: time-weighted return mapping functions --------------------

def test_get_twr_none_when_no_data():
    data = build_sample_data(snapshots=[])
    assert sensor_mapping.get_twr(data) is None
    attrs = sensor_mapping.get_twr_attributes(data)
    assert attrs["status"] == "no_data"
    assert attrs["periods_used"] == 0


def test_get_twr_returns_percentage_when_ok():
    from datetime import timedelta

    from custom_components.portfolio_engine.engine.models import Snapshot

    earlier = Snapshot(
        id="s1",
        portfolio_id="demo",
        timestamp=AS_OF - timedelta(days=30),
        portfolio_value=2000.0,
        cash_balance=500.0,
        invested=1500.0,
        base_currency="USD",
    )
    data = build_sample_data(snapshots=[earlier])

    assert sensor_mapping.get_twr(data) is not None
    assert isinstance(sensor_mapping.get_twr(data), float)
    attrs = sensor_mapping.get_twr_attributes(data)
    assert attrs["status"] == "ok"
    assert attrs["periods_used"] == 1
    assert attrs["as_of"] == AS_OF.isoformat()


def test_get_twr_none_when_not_ok_status():
    from custom_components.portfolio_engine.engine.models import Snapshot

    # single snapshot dated exactly at AS_OF - no elapsed time
    only_snapshot = Snapshot(
        id="s1",
        portfolio_id="demo",
        timestamp=AS_OF,
        portfolio_value=2500.0,
        cash_balance=1000.0,
        invested=1500.0,
        base_currency="USD",
    )
    data = build_sample_data(snapshots=[only_snapshot])

    assert sensor_mapping.get_twr(data) is None
    assert sensor_mapping.get_twr_attributes(data)["status"] == "insufficient_data"


# --- Milestone 7: dividend / drawdown / volatility / concentration -----------

def test_get_dividend_income_none_when_no_data():
    data = build_sample_data(transactions=[])
    assert sensor_mapping.get_dividend_income(data) is None
    assert sensor_mapping.get_dividend_attributes(data)["status"] == "no_data"


def test_get_dividend_income_when_ok():
    transactions = [
        Transaction(
            id="d1",
            portfolio_id="demo",
            type=TransactionType.DIVIDEND,
            date=AS_OF - timedelta(days=10),
            currency="USD",
            symbol="AAPL",
            amount=25.0,
        )
    ]
    data = build_sample_data(transactions=transactions)

    assert sensor_mapping.get_dividend_income(data) == 25.0
    attrs = sensor_mapping.get_dividend_attributes(data)
    assert attrs["status"] == "ok"
    assert attrs["lifetime"] == 25.0


def test_get_drawdown_none_when_no_data():
    data = build_sample_data(snapshots=[])
    assert sensor_mapping.get_drawdown(data) is None
    assert sensor_mapping.get_drawdown_attributes(data)["status"] == "no_data"


def test_get_drawdown_when_ok():
    from custom_components.portfolio_engine.engine.models import Snapshot

    snap = Snapshot(
        id="s1",
        portfolio_id="demo",
        timestamp=AS_OF - timedelta(days=10),
        portfolio_value=3000.0,
        cash_balance=1000.0,
        invested=2000.0,
        base_currency="USD",
    )
    data = build_sample_data(snapshots=[snap])

    # sample portfolio's current value (2500) is below the prior peak (3000)
    assert sensor_mapping.get_drawdown(data) is not None
    assert sensor_mapping.get_drawdown(data) < 0
    attrs = sensor_mapping.get_drawdown_attributes(data)
    assert attrs["status"] == "ok"
    assert attrs["peak_value"] == 3000.0


def test_get_volatility_insufficient_data_with_one_snapshot():
    from custom_components.portfolio_engine.engine.models import Snapshot

    snap = Snapshot(
        id="s1",
        portfolio_id="demo",
        timestamp=AS_OF - timedelta(days=10),
        portfolio_value=2000.0,
        cash_balance=1000.0,
        invested=1000.0,
        base_currency="USD",
    )
    data = build_sample_data(snapshots=[snap])

    assert sensor_mapping.get_volatility(data) is None
    assert sensor_mapping.get_volatility_attributes(data)["status"] == "insufficient_data"


def test_get_concentration_when_ok():
    data = build_sample_data()
    # sample portfolio has exactly one holding (AAPL) -> 100% concentration
    assert sensor_mapping.get_concentration(data) == 100.0
    attrs = sensor_mapping.get_concentration_attributes(data)
    assert attrs["status"] == "ok"
    assert attrs["largest_position"]["symbol"] == "AAPL"
    assert attrs["holding_count"] == 1


def test_twr_attributes_includes_annualized_pct():
    data = build_sample_data()
    attrs = sensor_mapping.get_twr_attributes(data)
    assert "annualized_pct" in attrs


# --- Milestone 9: last import -------------------------------------------------

def test_get_last_import_none_when_never_imported():
    data = build_sample_data()
    assert sensor_mapping.get_last_import(data) is None
    assert sensor_mapping.get_last_import_attributes(data)["status"] == "never_imported"


def test_get_last_import_when_a_report_exists():
    from custom_components.portfolio_engine.importers.report import ImportReport

    data = build_sample_data()
    data["last_import_report"] = ImportReport(
        provider_name="generic_csv",
        portfolio_id="demo",
        as_of=AS_OF,
        transactions_read=5,
        imported=[],
        duplicates=[],
        rejected=[],
    )
    # imported_count is derived from len(imported) == 0 here, deliberately
    # simple - just confirming the mapping function reads the report correctly.
    assert sensor_mapping.get_last_import(data) == 0
    attrs = sensor_mapping.get_last_import_attributes(data)
    assert attrs["status"] == "ok"
    assert attrs["provider"] == "generic_csv"
    assert attrs["transactions_read"] == 5


# --- Milestone 13 Phase 2: day change / allocation-by-type mapping functions --

def test_get_day_change_weighted_by_position_value():
    data = build_sample_data()
    # sample portfolio: 10 shares AAPL @ 150 (change_pct=2.0) = 1500 positions
    # value + 1000 cash (0% change) = 2500 total. Weighted: 2.0 * (1500/2500) = 1.2
    assert sensor_mapping.get_day_change(data) == 1.2


def test_get_day_change_is_never_none():
    # PerformanceResult has no status field - always a concrete float, even
    # for a transaction-less/snapshot-less portfolio (unlike MWR/TWR/etc).
    data = build_sample_data(transactions=[], snapshots=[])
    assert sensor_mapping.get_day_change(data) is not None
    assert isinstance(sensor_mapping.get_day_change(data), float)


def test_get_allocation_largest_group_is_state():
    data = build_sample_data()
    # sample portfolio: 1500 stock (AAPL) + 1000 cash = 2500 total.
    # stock = 60%, Cash = 40% - stock is the largest group.
    assert sensor_mapping.get_allocation(data) == 60.0


def test_get_allocation_attributes_shape_and_sorting():
    data = build_sample_data()
    attrs = sensor_mapping.get_allocation_attributes(data)

    assert attrs["largest_group"] == "stock"
    assert attrs["group_count"] == 2
    assert [g["label"] for g in attrs["allocation"]] == ["stock", "Cash"]  # largest-first
    assert attrs["allocation"][0] == {"label": "stock", "value": 1500.0, "pct": 60.0}
    assert attrs["allocation"][1] == {"label": "Cash", "value": 1000.0, "pct": 40.0}


def test_get_allocation_none_when_no_holdings_and_no_cash():
    # Directly assert the no-groups case using AllocationCalculator's own
    # documented behavior for an empty portfolio (no holdings, no cash) -
    # simpler than routing an empty portfolio through the full engine.
    from custom_components.portfolio_engine.engine.calculators.allocation_calculator import (
        AllocationCalculator,
    )
    from custom_components.portfolio_engine.engine.models import Portfolio

    data = build_sample_data()
    empty_portfolio = Portfolio(id="empty", name="Empty", cash_balance=0.0, holdings=[])
    data["allocation"] = AllocationCalculator(group_by="type").calculate(empty_portfolio, [])

    assert sensor_mapping.get_allocation(data) is None
    attrs = sensor_mapping.get_allocation_attributes(data)
    assert attrs["largest_group"] is None
    assert attrs["group_count"] == 0
    assert attrs["allocation"] == []
