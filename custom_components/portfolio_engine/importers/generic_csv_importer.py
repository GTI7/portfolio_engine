"""GenericCsvImporter - a documented, simple CSV schema for any broker
export a user can reshape into it (or hand-author from a statement), and
the fallback for brokers without a dedicated importer. See
docs/user/BROKER_IMPORT.md for the exact column documentation this
implementation follows.
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from ..engine.models import Transaction, TransactionType
from .base import BrokerImportProvider, ParseResult, RejectedRow
from .id_generation import deterministic_transaction_id

#: The exact column schema this importer expects (case-insensitive
#: header matching). Only `type`, `date`, `amount`, `currency` are always
#: required - `id`, `symbol`, `shares`, `price`, `notes` are optional,
#: with presence rules matching Transaction's own validation (e.g. `buy`
#: needs `symbol`/`shares`/`price`, `deposit` needs none of them).
REQUIRED_COLUMNS = {"type", "date", "amount", "currency"}


class GenericCsvImporter(BrokerImportProvider):
    name = "generic_csv"

    def parse(self, file_content: str, portfolio_id: str) -> ParseResult:
        # Milestone 10 QoL: defensive strip of a leading BOM character, in
        # case a caller other than the HA service (which reads files with
        # "utf-8-sig" and never produces one) passes BOM-prefixed text -
        # without this, the header row's first column parses as
        # '\ufeffid' instead of 'id', silently failing the required-column
        # check below.
        file_content = file_content.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(file_content))
        if reader.fieldnames is None:
            return ParseResult(warnings=["File is empty or has no header row."])

        normalized_fields = {f.strip().lower() for f in reader.fieldnames}
        missing = REQUIRED_COLUMNS - normalized_fields
        if missing:
            return ParseResult(
                warnings=[f"Missing required column(s): {', '.join(sorted(missing))}"]
            )

        transactions: list[Transaction] = []
        rejected: list[RejectedRow] = []

        for line_number, row in enumerate(reader, start=2):  # header is line 1
            normalized_row = {
                (k or "").strip().lower(): (v or "").strip() for k, v in row.items()
            }
            try:
                transactions.append(self._row_to_transaction(normalized_row, portfolio_id))
            except (ValueError, KeyError) as err:
                rejected.append(
                    RejectedRow(source_line=line_number, raw=normalized_row, error=str(err))
                )

        return ParseResult(transactions=transactions, rejected=rejected)

    def _row_to_transaction(self, row: dict[str, str], portfolio_id: str) -> Transaction:
        type_raw = row.get("type", "")
        try:
            txn_type = TransactionType(type_raw.lower())
        except ValueError as err:
            raise ValueError(f"unrecognized transaction type {type_raw!r}") from err

        date_raw = row.get("date", "")
        try:
            date = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        except ValueError as err:
            raise ValueError(f"unparseable date {date_raw!r} (expected ISO 8601)") from err
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)

        amount_raw = row.get("amount", "")
        try:
            amount = float(amount_raw)
        except ValueError as err:
            raise ValueError(f"unparseable amount {amount_raw!r}") from err

        currency = row.get("currency", "")
        symbol = row.get("symbol") or None
        shares = float(row["shares"]) if row.get("shares") else None
        price = float(row["price"]) if row.get("price") else None
        notes = row.get("notes") or None

        txn_id = row.get("id") or deterministic_transaction_id(
            txn_type.value, date.isoformat(), symbol, shares, amount, currency
        )

        return Transaction(
            id=txn_id,
            portfolio_id=portfolio_id,
            type=txn_type,
            date=date,
            currency=currency,
            amount=amount,
            symbol=symbol,
            shares=shares,
            price=price,
            notes=notes,
        )
