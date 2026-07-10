"""Assembles a BrokerImportProvider's ParseResult plus duplicate detection
against the existing transaction log into one ImportReport. Informational
only - see this module's docstring on build_import_report for why nothing
here writes to transactions.yaml or any other persisted state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import cast

from engine.models import Transaction, TransactionType

from .base import ParseResult, RejectedRow
from .duplicate_detection import DuplicateMatch, detect_duplicates


@dataclass
class ImportReport:
    """The complete, informational result of one import attempt. Nothing
    in this dataclass is ever written to transactions.yaml or any other
    persisted state automatically - see MILESTONE_9's own explicit scope
    boundary ("Do not automatically modify portfolio data") and
    docs/user/BROKER_IMPORT.md for the manual step a user takes after
    reviewing this report.
    """

    provider_name: str
    portfolio_id: str
    as_of: datetime
    transactions_read: int
    imported: list[Transaction] = field(default_factory=list)
    duplicates: list[DuplicateMatch] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return len(self.imported)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    def to_dict(self) -> dict[str, object]:
        """JSON-safe serialization, for Store-backed "last import" persistence
        in the HA layer (custom_components/portfolio_engine/import_report_store.py).
        Deliberately NOT a method on Transaction itself - Transaction's own
        serialization convention (Milestone 4) is that the repository layer
        owns it, since its primary storage target is hand-edited YAML, not
        JSON; ImportReport's target is Store (JSON-native, like Snapshot's -
        Milestone 6), so it owns its own serialization the same way Snapshot
        does, without adding anything to Transaction.
        """
        return {
            "provider_name": self.provider_name,
            "portfolio_id": self.portfolio_id,
            "as_of": self.as_of.isoformat(),
            "transactions_read": self.transactions_read,
            "imported": [_transaction_to_dict(t) for t in self.imported],
            "duplicates": [
                {
                    "imported": _transaction_to_dict(d.imported),
                    "matched_existing_id": d.matched_existing_id,
                    "reason": d.reason,
                }
                for d in self.duplicates
            ],
            "rejected": [
                {"source_line": r.source_line, "raw": r.raw, "error": r.error}
                for r in self.rejected
            ],
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ImportReport:
        imported_raw = cast("list[dict[str, object]]", data.get("imported") or [])
        duplicates_raw = cast("list[dict[str, object]]", data.get("duplicates") or [])
        rejected_raw = cast("list[dict[str, object]]", data.get("rejected") or [])
        warnings_raw = cast("list[str]", data.get("warnings") or [])

        return cls(
            provider_name=str(data["provider_name"]),
            portfolio_id=str(data["portfolio_id"]),
            as_of=datetime.fromisoformat(str(data["as_of"])),
            transactions_read=int(cast(str, data["transactions_read"])),
            imported=[_transaction_from_dict(t) for t in imported_raw],
            duplicates=[
                DuplicateMatch(
                    imported=_transaction_from_dict(
                        cast("dict[str, object]", d["imported"])
                    ),
                    matched_existing_id=str(d["matched_existing_id"]),
                    reason=str(d["reason"]),
                )
                for d in duplicates_raw
            ],
            rejected=[
                RejectedRow(
                    source_line=int(cast(str, r["source_line"])),
                    raw=cast("dict[str, str]", r["raw"]),
                    error=str(r["error"]),
                )
                for r in rejected_raw
            ],
            warnings=list(warnings_raw),
        )


def build_import_report(
    provider_name: str,
    portfolio_id: str,
    parse_result: ParseResult,
    existing_transactions: list[Transaction],
    as_of: datetime,
) -> ImportReport:
    """Pure function: given what a BrokerImportProvider parsed and the
    portfolio's current transaction log, decide which parsed transactions
    are genuinely new (`imported`) versus already-present (`duplicates`),
    alongside whatever `parse_result` already flagged as `rejected`
    (failed Transaction validation) or `warnings` (parsed but noteworthy).

    `transactions_read` counts every row the importer attempted to parse,
    successful or not (imported + duplicates + rejected == transactions_read
    always holds) - this is what answers "how many rows were actually in
    the file," distinct from how many ended up usable.
    """
    duplicates = detect_duplicates(parse_result.transactions, existing_transactions)
    duplicate_txn_ids = {d.imported.id for d in duplicates}
    imported = [t for t in parse_result.transactions if t.id not in duplicate_txn_ids]

    return ImportReport(
        provider_name=provider_name,
        portfolio_id=portfolio_id,
        as_of=as_of,
        transactions_read=len(parse_result.transactions) + len(parse_result.rejected),
        imported=imported,
        duplicates=duplicates,
        rejected=parse_result.rejected,
        warnings=parse_result.warnings,
    )


def _transaction_to_dict(txn: Transaction) -> dict[str, object]:
    """External serialization, not a Transaction method - see
    ImportReport.to_dict's docstring for why.
    """
    return {
        "id": txn.id,
        "portfolio_id": txn.portfolio_id,
        "type": txn.type.value,
        "date": txn.date.isoformat(),
        "currency": txn.currency,
        "amount": txn.amount,
        "symbol": txn.symbol,
        "shares": txn.shares,
        "price": txn.price,
        "notes": txn.notes,
    }


def _transaction_from_dict(data: dict[str, object]) -> Transaction:
    return Transaction(
        id=str(data["id"]),
        portfolio_id=str(data["portfolio_id"]),
        type=TransactionType(str(data["type"])),
        date=datetime.fromisoformat(str(data["date"])),
        currency=str(data["currency"]),
        amount=float(cast(str, data["amount"])),
        symbol=str(data["symbol"]) if data.get("symbol") is not None else None,
        shares=float(cast(str, data["shares"])) if data.get("shares") is not None else None,
        price=float(cast(str, data["price"])) if data.get("price") is not None else None,
        notes=str(data["notes"]) if data.get("notes") is not None else None,
    )
