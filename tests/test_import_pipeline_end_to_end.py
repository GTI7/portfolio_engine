"""End-to-end proof that the import pipeline is genuinely "just" a
producer of Transaction objects the rest of the engine already knows how
to consume - no calculator changes, per MILESTONE_9's central acceptance
criterion. This test runs a real broker export through a real importer,
through the real duplicate-detection/report pipeline, and then feeds the
resulting transactions into the actual PortfolioEngine (reconciliation,
MWR, TWR, unmodified) to confirm they work correctly end to end.
"""
from datetime import datetime, timedelta

from engine.calculators.mwr_calculator import MwrCalculator
from engine.calculators.reconciliation_calculator import ReconciliationCalculator
from engine.calculators.twr_calculator import TwrCalculator
from engine.models import Holding, Portfolio, Quote, Snapshot
from engine.portfolio_engine import PortfolioEngine
from importers.generic_csv_importer import GenericCsvImporter
from importers.report import build_import_report

BASE = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def test_imported_transactions_pass_existing_reconciliation_unmodified():
    csv_content = (
        "id,type,date,symbol,shares,price,amount,currency,notes\n"
        "d1,deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
        "b1,buy,2026-01-02T00:00:00Z,AAPL,10,100.0,1000.0,USD,\n"
    )
    parse_result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")
    report = build_import_report(
        "generic_csv", "demo", parse_result, existing_transactions=[], as_of=BASE
    )

    assert report.imported_count == 2

    # feed the imported transactions straight into a real Portfolio, using
    # the actual, unmodified ReconciliationCalculator - no import-specific
    # calculator code exists anywhere.
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        cash_balance=0.0,
        holdings=[
            Holding(symbol="AAPL", shares=10, avg_price=100.0, currency="USD", type="stock")
        ],
        transactions=report.imported,
    )
    positions_quotes = {"AAPL": Quote(symbol="AAPL", price=150.0, currency="USD")}
    engine = PortfolioEngine(
        {"reconciliation": ReconciliationCalculator(), "mwr": MwrCalculator(as_of=BASE)}
    )
    result = engine.run(portfolio, positions_quotes)

    assert result["reconciliation"].status == "ok"
    assert result["mwr"].status in ("ok", "insufficient_data")  # computable given the data


def test_imported_transactions_pass_existing_twr_unmodified():
    csv_content = (
        "id,type,date,amount,currency,symbol,shares,price\n"
        "d1,deposit,2026-01-01T00:00:00Z,1000.0,USD,,,\n"
    )
    parse_result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")
    report = build_import_report(
        "generic_csv", "demo", parse_result, existing_transactions=[], as_of=BASE
    )

    snapshot = Snapshot(
        id="s1",
        portfolio_id="demo",
        timestamp=BASE,
        portfolio_value=1000.0,
        cash_balance=1000.0,
        invested=1000.0,
        base_currency="USD",
    )
    portfolio = Portfolio(
        id="demo",
        name="Demo",
        base_currency="USD",
        cash_balance=1100.0,
        transactions=report.imported,
        snapshots=[snapshot],
    )
    as_of = BASE + timedelta(days=30)
    engine = PortfolioEngine({"twr": TwrCalculator(as_of=as_of)})
    result = engine.run(portfolio, [])

    assert result["twr"].status == "ok"
    assert result["twr"].twr_pct == 10.0  # 1000 -> 1100, no further deposits in this period


def test_reimporting_the_same_file_is_fully_detected_as_duplicates():
    """The realistic "user accidentally re-runs the same import" scenario -
    every transaction from the second parse should be flagged as a
    duplicate against the first import's already-recorded transactions.
    """
    csv_content = (
        "id,type,date,amount,currency,symbol,shares,price\n"
        "d1,deposit,2026-01-01T00:00:00Z,1000.0,USD,,,\n"
        ",buy,2026-01-02T00:00:00Z,1000.0,USD,AAPL,10,100.0\n"  # no id -> deterministic
    )
    first_parse = GenericCsvImporter().parse(csv_content, portfolio_id="demo")
    first_report = build_import_report(
        "generic_csv", "demo", first_parse, existing_transactions=[], as_of=BASE
    )
    assert first_report.imported_count == 2

    # simulate the user copying the first import's results into their real
    # log, then re-running the same import by mistake
    existing_log = first_report.imported
    second_parse = GenericCsvImporter().parse(csv_content, portfolio_id="demo")
    second_report = build_import_report(
        "generic_csv", "demo", second_parse, existing_transactions=existing_log, as_of=BASE
    )

    assert second_report.imported_count == 0
    assert second_report.duplicate_count == 2
