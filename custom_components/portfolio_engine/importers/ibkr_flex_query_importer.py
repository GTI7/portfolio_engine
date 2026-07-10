"""IbkrFlexQueryImporter - parses Interactive Brokers Activity Flex Query
XML exports (Trades and CashTransactions sections).

Targets the standard field names IBKR's Flex Query XML uses for these two
sections (`symbol`, `tradeDate`, `quantity`, `tradePrice`, `buySell`,
`ibCommission`, `currency`, `transactionID` for Trade; `type`, `symbol`,
`amount`, `dateTime`, `currency`, `transactionID` for CashTransaction) -
these are IBKR's own standard/default field names, but Flex Query
templates are user-configurable, so a heavily customized template that
renames or omits fields may need adjustment. See
docs/user/BROKER_IMPORT.md for what this importer expects and how to
configure a compatible Flex Query template.

CashTransaction `type` values recognized: "Dividends" -> DIVIDEND,
"Deposits/Withdrawals" -> DEPOSIT or WITHDRAWAL (by amount sign, since
IBKR reports these as signed - positive credit, negative debit),
"Fees"/"Other Fees" -> FEE. Any other CashTransaction type (broker
interest, withholding tax, etc.) is skipped with a warning, not rejected
- these aren't invalid data, just outside this project's TransactionType
vocabulary (Milestone 4).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime

from ..engine.models import Transaction, TransactionType
from .base import BrokerImportProvider, ParseResult, RejectedRow

_CASH_TYPE_DIVIDEND = "dividends"
_CASH_TYPE_DEPOSIT_WITHDRAWAL = {"deposits/withdrawals", "deposits & withdrawals"}
_CASH_TYPE_FEE = {"fees", "other fees"}


class IbkrFlexQueryImporter(BrokerImportProvider):
    name = "ibkr_flex_query"

    def parse(self, file_content: str, portfolio_id: str) -> ParseResult:
        try:
            root = ET.fromstring(file_content)  # noqa: S314 - broker export, not untrusted web input
        except ET.ParseError as err:
            return ParseResult(warnings=[f"Could not parse XML: {err}"])

        transactions: list[Transaction] = []
        rejected: list[RejectedRow] = []
        skipped_cash_types: Counter[str] = Counter()
        line = 0  # Flex Query XML has no natural line-per-record; use a running counter instead

        for trade_el in root.iter("Trade"):
            line += 1
            try:
                transactions.append(self._trade_to_transaction(trade_el, portfolio_id))
            except (ValueError, KeyError) as err:
                rejected.append(
                    RejectedRow(source_line=line, raw=dict(trade_el.attrib), error=str(err))
                )

        for cash_el in root.iter("CashTransaction"):
            line += 1
            cash_type = (cash_el.attrib.get("type") or "").strip().lower()
            if cash_type == _CASH_TYPE_DIVIDEND:
                txn_type: TransactionType | None = TransactionType.DIVIDEND
            elif cash_type in _CASH_TYPE_DEPOSIT_WITHDRAWAL:
                txn_type = None  # decided per-row below, by amount sign
            elif cash_type in _CASH_TYPE_FEE:
                txn_type = TransactionType.FEE
            else:
                skipped_cash_types[cash_el.attrib.get("type", "unknown")] += 1
                continue

            try:
                transactions.append(
                    self._cash_transaction_to_transaction(cash_el, portfolio_id, txn_type)
                )
            except (ValueError, KeyError) as err:
                rejected.append(
                    RejectedRow(source_line=line, raw=dict(cash_el.attrib), error=str(err))
                )

        warnings = [
            f"Skipped {count} cash transaction(s) of unsupported type {cash_type!r} "
            "(not a recognized Portfolio Engine transaction category)"
            for cash_type, count in sorted(skipped_cash_types.items())
        ]

        return ParseResult(transactions=transactions, rejected=rejected, warnings=warnings)

    def _trade_to_transaction(self, el: ET.Element, portfolio_id: str) -> Transaction:
        attrib = el.attrib

        buy_sell = (attrib.get("buySell") or "").strip().upper()
        if buy_sell == "BUY":
            txn_type = TransactionType.BUY
        elif buy_sell == "SELL":
            txn_type = TransactionType.SELL
        else:
            raise ValueError(f"unrecognized buySell value {buy_sell!r}")

        symbol = attrib.get("symbol")
        if not symbol:
            raise ValueError("Trade element missing symbol")

        quantity = _require_float(attrib, "quantity")
        price = _require_float(attrib, "tradePrice")
        shares = abs(quantity)

        trade_money = attrib.get("tradeMoney") or attrib.get("proceeds")
        amount = abs(float(trade_money)) if trade_money else abs(price * shares)

        date_raw = attrib.get("tradeDate") or attrib.get("dateTime")
        if not date_raw:
            raise ValueError("Trade element missing tradeDate")
        date = _parse_ibkr_date(date_raw)

        currency = attrib.get("currency")
        if not currency:
            raise ValueError("Trade element missing currency")

        txn_id = attrib.get("transactionID") or attrib.get("tradeID")
        if not txn_id:
            raise ValueError("Trade element missing transactionID")

        return Transaction(
            id=f"ibkr-{txn_id}",
            portfolio_id=portfolio_id,
            type=txn_type,
            date=date,
            currency=currency,
            amount=amount,
            symbol=symbol,
            shares=shares,
            price=price,
        )

    def _cash_transaction_to_transaction(
        self, el: ET.Element, portfolio_id: str, txn_type: TransactionType | None
    ) -> Transaction:
        attrib = el.attrib

        amount_signed = _require_float(attrib, "amount")
        if txn_type is None:  # Deposits/Withdrawals - direction is the amount's own sign
            txn_type = (
                TransactionType.DEPOSIT if amount_signed >= 0 else TransactionType.WITHDRAWAL
            )

        date_raw = attrib.get("dateTime") or attrib.get("settleDate")
        if not date_raw:
            raise ValueError("CashTransaction element missing dateTime")
        date = _parse_ibkr_date(date_raw)

        currency = attrib.get("currency")
        if not currency:
            raise ValueError("CashTransaction element missing currency")

        txn_id = attrib.get("transactionID")
        if not txn_id:
            raise ValueError("CashTransaction element missing transactionID")

        symbol = attrib.get("symbol") or None
        # DIVIDEND is the only cash-transaction type that carries a symbol
        # in Transaction's own validation rules (engine/models.py) - drop
        # it for FEE/DEPOSIT/WITHDRAWAL even if IBKR's export includes one,
        # so Transaction's own validation doesn't reject an otherwise-valid row.
        if txn_type is not TransactionType.DIVIDEND:
            symbol = None

        return Transaction(
            id=f"ibkr-{txn_id}",
            portfolio_id=portfolio_id,
            type=txn_type,
            date=date,
            currency=currency,
            amount=abs(amount_signed),
            symbol=symbol,
        )


def _require_float(attrib: dict[str, str], key: str) -> float:
    raw = attrib.get(key)
    if raw is None or raw == "":
        raise ValueError(f"missing required field {key!r}")
    try:
        return float(raw)
    except ValueError as err:
        raise ValueError(f"unparseable {key} value {raw!r}") from err


def _parse_ibkr_date(raw: str) -> datetime:
    """IBKR Flex Query dates commonly appear as YYYYMMDD ("20260115"),
    YYYYMMDD;HHMMSS ("20260115;093000"), or plain ISO ("2026-01-15") -
    tries each in turn rather than assuming one specific template output.
    """
    candidate = raw.split(";")[0].strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(candidate, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError as err:
        raise ValueError(f"unparseable IBKR date {raw!r}") from err
