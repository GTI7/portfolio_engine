from datetime import datetime, timedelta

from engine.models import Transaction, TransactionType
from importers.base import ParseResult, RejectedRow
from importers.duplicate_detection import DuplicateMatch, detect_duplicates
from importers.id_generation import deterministic_transaction_id
from importers.report import ImportReport, build_import_report

BASE = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def txn(offset_days=0, type_=TransactionType.DEPOSIT, txn_id=None, **kwargs):
    defaults = dict(
        id=txn_id or f"t-{offset_days}",
        portfolio_id="demo",
        type=type_,
        date=BASE + timedelta(days=offset_days),
        currency="USD",
        amount=100.0,
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


# --- deterministic_transaction_id ------------------------------------------

def test_deterministic_id_is_stable_across_calls():
    id1 = deterministic_transaction_id("buy", BASE.isoformat(), "AAPL", 10.0, 1000.0, "USD")
    id2 = deterministic_transaction_id("buy", BASE.isoformat(), "AAPL", 10.0, 1000.0, "USD")
    assert id1 == id2


def test_deterministic_id_differs_for_different_content():
    id1 = deterministic_transaction_id("buy", BASE.isoformat(), "AAPL", 10.0, 1000.0, "USD")
    id2 = deterministic_transaction_id("buy", BASE.isoformat(), "AAPL", 11.0, 1000.0, "USD")
    assert id1 != id2


def test_deterministic_id_has_gen_prefix():
    result = deterministic_transaction_id("deposit", BASE.isoformat(), None, None, 500.0, "USD")
    assert result.startswith("gen-")


# --- detect_duplicates -------------------------------------------------------

def test_no_duplicates_when_ids_and_content_differ():
    imported = [txn(0, txn_id="new-1", amount=100.0)]
    existing = [txn(0, txn_id="old-1", amount=999.0)]
    matches = detect_duplicates(imported, existing)
    assert matches == []


def test_exact_id_match_is_a_duplicate():
    imported = [txn(0, txn_id="shared-id", amount=100.0)]
    existing = [txn(5, txn_id="shared-id", amount=999.0)]  # different date/amount, same id
    matches = detect_duplicates(imported, existing)
    assert len(matches) == 1
    assert matches[0].reason == "id"
    assert matches[0].matched_existing_id == "shared-id"


def test_heuristic_match_on_matching_content_different_ids():
    imported = [
        txn(
            0,
            txn_id="gen-abc",
            type_=TransactionType.BUY,
            symbol="AAPL",
            shares=10,
            price=100.0,
            amount=1000.0,
        )
    ]
    existing = [
        txn(
            0,
            txn_id="ibkr-ref-999",
            type_=TransactionType.BUY,
            symbol="AAPL",
            shares=10,
            price=100.0,
            amount=1000.0,
        )
    ]
    matches = detect_duplicates(imported, existing)
    assert len(matches) == 1
    assert matches[0].reason == "heuristic"
    assert matches[0].matched_existing_id == "ibkr-ref-999"


def test_heuristic_tolerates_tiny_floating_point_differences():
    imported = [
        txn(
            0, txn_id="a", type_=TransactionType.BUY, symbol="AAPL",
            shares=10.0, price=100.0, amount=1000.001,
        )
    ]
    existing = [
        txn(
            0, txn_id="b", type_=TransactionType.BUY, symbol="AAPL",
            shares=10.0, price=100.0, amount=1000.0,
        )
    ]
    matches = detect_duplicates(imported, existing)
    assert len(matches) == 1
    assert matches[0].reason == "heuristic"


def test_heuristic_does_not_match_different_dates():
    kwargs = dict(type_=TransactionType.BUY, symbol="AAPL", shares=10.0, price=100.0, amount=1000.0)
    imported = [txn(0, txn_id="a", **kwargs)]
    existing = [txn(1, txn_id="b", **kwargs)]
    matches = detect_duplicates(imported, existing)
    assert matches == []


def test_heuristic_does_not_match_different_symbols():
    kwargs = dict(type_=TransactionType.BUY, shares=10.0, price=100.0, amount=1000.0)
    imported = [txn(0, txn_id="a", symbol="AAPL", **kwargs)]
    existing = [txn(0, txn_id="b", symbol="MSFT", **kwargs)]
    matches = detect_duplicates(imported, existing)
    assert matches == []


def test_deposit_without_symbol_or_shares_can_still_heuristic_match():
    imported = [
        Transaction(
            id="gen-1",
            portfolio_id="demo",
            type=TransactionType.DEPOSIT,
            date=BASE,
            currency="USD",
            amount=1000.0,
        )
    ]
    existing = [
        Transaction(
            id="manual-1",
            portfolio_id="demo",
            type=TransactionType.DEPOSIT,
            date=BASE,
            currency="USD",
            amount=1000.0,
        )
    ]
    matches = detect_duplicates(imported, existing)
    assert len(matches) == 1
    assert matches[0].reason == "heuristic"


def test_empty_existing_log_produces_no_duplicates():
    imported = [txn(0, txn_id="a")]
    matches = detect_duplicates(imported, [])
    assert matches == []


# --- build_import_report -----------------------------------------------------

def test_report_counts_are_consistent():
    parse_result = ParseResult(
        transactions=[
            txn(0, txn_id="new-1", amount=100.0),
            txn(1, txn_id="dup-1", amount=200.0),
        ],
        rejected=[RejectedRow(source_line=3, raw={"type": "bogus"}, error="unknown type")],
        warnings=["row 4 had an unrecognized column, ignored"],
    )
    existing = [txn(1, txn_id="dup-1", amount=200.0)]  # matches the second parsed txn exactly

    report = build_import_report("test-provider", "demo", parse_result, existing, as_of=BASE)

    assert report.transactions_read == 3  # 2 parsed + 1 rejected
    assert report.imported_count == 1
    assert report.duplicate_count == 1
    assert report.rejected_count == 1
    assert report.warnings == ["row 4 had an unrecognized column, ignored"]
    assert report.imported[0].id == "new-1"


def test_report_with_no_duplicates_or_rejections():
    parse_result = ParseResult(transactions=[txn(0, txn_id="a"), txn(1, txn_id="b")])
    report = build_import_report("test-provider", "demo", parse_result, [], as_of=BASE)

    assert report.transactions_read == 2
    assert report.imported_count == 2
    assert report.duplicate_count == 0
    assert report.rejected_count == 0


def test_report_all_rejected():
    parse_result = ParseResult(
        rejected=[
            RejectedRow(source_line=1, raw={}, error="missing type"),
            RejectedRow(source_line=2, raw={}, error="missing date"),
        ]
    )
    report = build_import_report("test-provider", "demo", parse_result, [], as_of=BASE)

    assert report.transactions_read == 2
    assert report.imported_count == 0
    assert report.rejected_count == 2


# --- ImportReport serialization (Store-backed persistence) -------------------

def test_report_round_trips_through_dict():
    parse_result = ParseResult(
        transactions=[txn(0, txn_id="new-1", amount=100.0)],
        rejected=[RejectedRow(source_line=3, raw={"type": "bogus"}, error="unknown type")],
        warnings=["a warning"],
    )
    existing = [txn(1, txn_id="dup-1", amount=200.0)]
    original = build_import_report("generic_csv", "demo", parse_result, existing, as_of=BASE)

    restored = ImportReport.from_dict(original.to_dict())

    assert restored.provider_name == original.provider_name
    assert restored.portfolio_id == original.portfolio_id
    assert restored.as_of == original.as_of
    assert restored.transactions_read == original.transactions_read
    assert restored.imported_count == original.imported_count
    assert restored.imported[0].id == original.imported[0].id
    assert restored.warnings == original.warnings


def test_report_with_duplicates_round_trips():
    imported_txn = txn(0, txn_id="new-1")
    report = ImportReport(
        provider_name="test",
        portfolio_id="demo",
        as_of=BASE,
        transactions_read=1,
        duplicates=[
            DuplicateMatch(imported=imported_txn, matched_existing_id="old-1", reason="id")
        ],
    )
    restored = ImportReport.from_dict(report.to_dict())

    assert len(restored.duplicates) == 1
    assert restored.duplicates[0].matched_existing_id == "old-1"
    assert restored.duplicates[0].reason == "id"
    assert restored.duplicates[0].imported.id == "new-1"


def test_report_to_dict_is_json_safe():
    """Confirms the shape is actually JSON-serializable (not just plain
    Python dicts) - the real requirement for Store-backed persistence.
    """
    import json

    parse_result = ParseResult(transactions=[txn(0, txn_id="a")])
    report = build_import_report("generic_csv", "demo", parse_result, [], as_of=BASE)

    serialized = json.dumps(report.to_dict())
    restored = ImportReport.from_dict(json.loads(serialized))

    assert restored.imported[0].id == "a"
