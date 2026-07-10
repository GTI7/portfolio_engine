import pytest

from custom_components.portfolio_engine.engine.calculators.allocation_calculator import (
    AllocationCalculator,
)
from custom_components.portfolio_engine.engine.calculators.mwr_calculator import MwrCalculator
from custom_components.portfolio_engine.engine.calculators.performance_calculator import (
    PerformanceCalculator,
)
from custom_components.portfolio_engine.engine.calculators.portfolio_calculator import (
    PortfolioCalculator,
)
from custom_components.portfolio_engine.engine.calculators.reconciliation_calculator import (
    ReconciliationCalculator,
)
from custom_components.portfolio_engine.engine.calculators.transaction_calculator import (
    TransactionCalculator,
)
from custom_components.portfolio_engine.engine.calculators.twr_calculator import TwrCalculator
from custom_components.portfolio_engine.engine.models import Holding, Portfolio, Quote
from custom_components.portfolio_engine.engine.portfolio_engine import PortfolioEngine
from custom_components.portfolio_engine.update_logic import (
    PortfolioDataUnavailable,
    async_fetch_portfolio_data,
)


class FakeRepository:
    def __init__(self, portfolios):
        self._portfolios = portfolios

    async def async_get_portfolios(self):
        return self._portfolios

    name = "fake"


class FakeProvider:
    def __init__(self, quotes):
        self._quotes = quotes

    async def async_get_quotes(self, symbols):
        return {s: q for s, q in self._quotes.items() if s in symbols}

    name = "fake"


class FakeCurrencyProvider:
    def __init__(self, rates=None, calls=None):
        self._rates = rates or {}
        self._calls = calls if calls is not None else []

    async def async_get_rates(self, base, targets):
        self._calls.append((base, tuple(targets)))
        result = {base: 1.0}
        result.update({k: v for k, v in self._rates.items() if k in targets})
        return result

    name = "fake"


class FakeSnapshotRepository:
    """In-memory stand-in for SnapshotRepository - mirrors
    repositories/in_memory_snapshot_repository.py's behavior (append-only,
    duplicate-id rejection) but defined locally since it's test-only and
    this file already follows a local-fakes pattern for the other
    dependencies.
    """

    def __init__(self, snapshots=None):
        self._snapshots = list(snapshots or [])
        self.appended = []

    async def async_get_snapshots(self, portfolio_id):
        return [s for s in self._snapshots if s.portfolio_id == portfolio_id]

    async def async_append_snapshot(self, snapshot):
        if any(s.id == snapshot.id for s in self._snapshots):
            raise ValueError(f"duplicate snapshot id {snapshot.id!r}")
        self._snapshots.append(snapshot)
        self.appended.append(snapshot)

    name = "fake"


def build_engine() -> PortfolioEngine:
    return PortfolioEngine(
        {
            "summary": PortfolioCalculator(),
            "allocation": AllocationCalculator(group_by="type"),
            "performance": PerformanceCalculator(),
            "reconciliation": ReconciliationCalculator(),
            "transactions": TransactionCalculator(),
            "mwr": MwrCalculator(),
            "twr": TwrCalculator(),
        }
    )


@pytest.mark.asyncio
async def test_fetches_first_portfolio_and_runs_engine():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        cash_balance=500.0,
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock")],
    )
    repo = FakeRepository([portfolio])
    provider = FakeProvider(
        {"AAPL": Quote(symbol="AAPL", price=150, currency="USD", change_pct=1.0)}
    )
    currency_provider = FakeCurrencyProvider()
    snapshot_repo = FakeSnapshotRepository()

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["portfolio_id"] == "demo"
    assert result["base_currency"] == "USD"
    assert result["summary"].cash_balance == 500.0
    assert result["symbols_requested"] == 1
    assert result["symbols_missing_quotes"] == []
    assert result["fx_rates_missing"] == []


@pytest.mark.asyncio
async def test_raises_when_no_portfolios_configured():
    repo = FakeRepository([])
    provider = FakeProvider({})
    currency_provider = FakeCurrencyProvider()
    snapshot_repo = FakeSnapshotRepository()

    with pytest.raises(PortfolioDataUnavailable):
        await async_fetch_portfolio_data(
            repo, provider, currency_provider, snapshot_repo, build_engine()
        )


@pytest.mark.asyncio
async def test_reports_missing_quotes_without_raising():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        holdings=[
            Holding(symbol="AAPL", shares=1, avg_price=100, currency="USD", type="stock"),
            Holding(symbol="GHOST", shares=1, avg_price=100, currency="USD", type="stock"),
        ],
    )
    repo = FakeRepository([portfolio])
    # provider only knows about AAPL - GHOST has no quote available
    provider = FakeProvider({"AAPL": Quote(symbol="AAPL", price=150, currency="USD")})
    currency_provider = FakeCurrencyProvider()
    snapshot_repo = FakeSnapshotRepository()

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["symbols_missing_quotes"] == ["GHOST"]
    # engine still computes something for the missing symbol (price defaults
    # to 0) rather than the whole update failing over one bad quote
    assert len(result["positions"]) == 2


@pytest.mark.asyncio
async def test_single_currency_portfolio_never_calls_currency_provider():
    """Same-currency portfolios shouldn't pay any FX lookup cost at all."""
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        holdings=[Holding(symbol="AAPL", shares=1, avg_price=100, currency="USD", type="stock")],
    )
    repo = FakeRepository([portfolio])
    provider = FakeProvider({"AAPL": Quote(symbol="AAPL", price=150, currency="USD")})
    calls = []
    currency_provider = FakeCurrencyProvider(calls=calls)
    snapshot_repo = FakeSnapshotRepository()

    await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert calls == []


@pytest.mark.asyncio
async def test_multi_currency_portfolio_fetches_and_applies_fx_rates():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="EUR",
        holdings=[
            Holding(symbol="MC.PA", shares=1, avg_price=600.0, currency="EUR", type="stock"),
            Holding(symbol="AAPL", shares=10, avg_price=150.0, currency="USD", type="stock"),
        ],
    )
    repo = FakeRepository([portfolio])
    provider = FakeProvider(
        {
            "MC.PA": Quote(symbol="MC.PA", price=650.0, currency="EUR"),
            "AAPL": Quote(symbol="AAPL", price=200.0, currency="USD"),
        }
    )
    calls = []
    currency_provider = FakeCurrencyProvider(rates={"USD": 0.92}, calls=calls)
    snapshot_repo = FakeSnapshotRepository()

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert calls == [("EUR", ("USD",))]  # only the foreign currency was requested
    assert result["fx_rates"] == {"EUR": 1.0, "USD": 0.92}
    assert result["fx_rates_missing"] == []

    positions = {p.symbol: p for p in result["positions"]}
    assert positions["AAPL"].fx_rate == 0.92
    assert positions["AAPL"].market_value_base == round(10 * 200.0 * 0.92, 2)


@pytest.mark.asyncio
async def test_missing_fx_rate_is_reported_not_silently_dropped():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="EUR",
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=150.0, currency="USD", type="stock")],
    )
    repo = FakeRepository([portfolio])
    provider = FakeProvider({"AAPL": Quote(symbol="AAPL", price=200.0, currency="USD")})
    # currency_provider knows no rates at all - USD will be missing
    currency_provider = FakeCurrencyProvider(rates={})
    snapshot_repo = FakeSnapshotRepository()

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["fx_rates_missing"] == ["USD"]
    # engine still ran (best-effort fallback to rate 1.0), didn't crash
    assert len(result["positions"]) == 1


# --- Milestone 6: snapshot collection -----------------------------------------

@pytest.mark.asyncio
async def test_first_run_creates_a_snapshot():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        cash_balance=500.0,
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock")],
    )
    repo = FakeRepository([portfolio])
    provider = FakeProvider({"AAPL": Quote(symbol="AAPL", price=150, currency="USD")})
    currency_provider = FakeCurrencyProvider()
    snapshot_repo = FakeSnapshotRepository()

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["snapshot_created"] is True
    assert len(snapshot_repo.appended) == 1
    assert snapshot_repo.appended[0].portfolio_id == "demo"
    assert len(result["snapshots"]) == 1


@pytest.mark.asyncio
async def test_second_run_same_day_does_not_create_a_duplicate():
    from datetime import UTC, datetime

    from custom_components.portfolio_engine.engine.models import Snapshot

    portfolio = Portfolio(id="demo", name="Demo", base_currency="USD", cash_balance=500.0)
    repo = FakeRepository([portfolio])
    provider = FakeProvider({})
    currency_provider = FakeCurrencyProvider()
    existing = Snapshot(
        id="existing",
        portfolio_id="demo",
        timestamp=datetime.now(UTC),
        portfolio_value=500.0,
        cash_balance=500.0,
        invested=0.0,
        base_currency="USD",
    )
    snapshot_repo = FakeSnapshotRepository(snapshots=[existing])

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["snapshot_created"] is False
    assert snapshot_repo.appended == []
    assert len(result["snapshots"]) == 1  # still just the pre-existing one


@pytest.mark.asyncio
async def test_engine_receives_existing_snapshots_via_portfolio():
    """Confirms portfolio.snapshots is actually populated before engine.run()
    - not just that the repository was called, but that TwrCalculator (or
    any calculator) would see the data.
    """
    from datetime import UTC, datetime, timedelta

    from custom_components.portfolio_engine.engine.models import Snapshot

    portfolio = Portfolio(id="demo", name="Demo", base_currency="USD", cash_balance=1000.0)
    repo = FakeRepository([portfolio])
    provider = FakeProvider({})
    currency_provider = FakeCurrencyProvider()
    yesterday = datetime.now(UTC) - timedelta(days=1)
    existing = Snapshot(
        id="existing",
        portfolio_id="demo",
        timestamp=yesterday,
        portfolio_value=900.0,
        cash_balance=900.0,
        invested=0.0,
        base_currency="USD",
    )
    snapshot_repo = FakeSnapshotRepository(snapshots=[existing])

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    # TWR should have used the pre-existing snapshot as a real boundary
    assert result["twr"].status == "ok"
    assert result["twr"].periods_used == 1


# --- Milestone 8: snapshot repository graceful degradation -------------------

class FailingSnapshotRepository:
    """A SnapshotRepository whose calls always raise - simulates a broken
    Store backend (corrupted data, disk I/O error, etc.).
    """

    def __init__(self, fail_on_read=True, fail_on_write=True):
        self._fail_on_read = fail_on_read
        self._fail_on_write = fail_on_write

    async def async_get_snapshots(self, portfolio_id):
        if self._fail_on_read:
            raise RuntimeError("simulated storage read failure")
        return []

    async def async_append_snapshot(self, snapshot):
        if self._fail_on_write:
            raise RuntimeError("simulated storage write failure")

    name = "failing"


@pytest.mark.asyncio
async def test_snapshot_read_failure_does_not_fail_the_whole_refresh():
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        cash_balance=1000.0,
        holdings=[Holding(symbol="AAPL", shares=10, avg_price=100, currency="USD", type="stock")],
    )
    repo = FakeRepository([portfolio])
    provider = FakeProvider({"AAPL": Quote(symbol="AAPL", price=150, currency="USD")})
    currency_provider = FakeCurrencyProvider()
    snapshot_repo = FailingSnapshotRepository(fail_on_read=True)

    # should NOT raise, despite the snapshot repository being completely broken
    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["snapshot_repository_error"] == "simulated storage read failure"
    assert result["snapshots"] == []
    assert result["snapshot_created"] is False
    # everything else still works normally
    assert result["summary"].total_value == 1500.0 + 1000.0
    assert len(result["positions"]) == 1


@pytest.mark.asyncio
async def test_snapshot_write_failure_does_not_fail_the_whole_refresh():
    portfolio = Portfolio(id="demo", name="Demo", base_currency="USD", cash_balance=1000.0)
    repo = FakeRepository([portfolio])
    provider = FakeProvider({})
    currency_provider = FakeCurrencyProvider()
    snapshot_repo = FailingSnapshotRepository(fail_on_read=False, fail_on_write=True)

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["snapshot_repository_error"] == "simulated storage write failure"
    assert result["snapshot_created"] is False
    assert result["summary"].total_value == 1000.0  # engine output unaffected


@pytest.mark.asyncio
async def test_successful_snapshot_repository_has_no_error():
    portfolio = Portfolio(id="demo", name="Demo", base_currency="USD", cash_balance=1000.0)
    repo = FakeRepository([portfolio])
    provider = FakeProvider({})
    currency_provider = FakeCurrencyProvider()
    snapshot_repo = FakeSnapshotRepository()

    result = await async_fetch_portfolio_data(
        repo, provider, currency_provider, snapshot_repo, build_engine()
    )

    assert result["snapshot_repository_error"] is None
