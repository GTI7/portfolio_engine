"""External cash-flow classification, shared by MwrCalculator and
TwrCalculator - both need "which transactions represent capital crossing
the boundary between the investor and the portfolio," and both must use
the exact same answer or their return figures would be inconsistent with
each other for no good reason. See
docs/adr/0011-mwr-external-cash-flow-classification.md for the full
reasoning behind this specific classification; this module is the single
implementation of that decision, not a second copy of it.
"""
from __future__ import annotations

from datetime import datetime

from .models import Transaction, TransactionType

#: Which transaction types contribute an external cash flow, and their
#: sign convention (negative = capital into the portfolio, positive =
#: capital out) - BUY/SELL/DIVIDEND/FEE are deliberately absent: they're
#: internal to the portfolio and already reflected in its value.
EXTERNAL_FLOW_SIGN: dict[TransactionType, int] = {
    TransactionType.DEPOSIT: -1,
    TransactionType.WITHDRAWAL: 1,
    TransactionType.TRANSFER_IN: -1,
    TransactionType.TRANSFER_OUT: 1,
}


def flow_magnitude(txn: Transaction) -> float:
    """TRANSFER_IN/TRANSFER_OUT's Transaction.amount is always 0.0 (no
    cash moves in a transfer) - their economically real magnitude for
    return calculations is the value of the shares moved, not the literal
    (zero) cash amount.
    """
    if txn.type in (TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT):
        assert txn.shares is not None and txn.price is not None
        return txn.shares * txn.price
    return txn.amount


def extract_external_cash_flows(transactions: list[Transaction]) -> list[tuple[datetime, float]]:
    """Return every external cash flow as a (date, signed amount) pair,
    in whatever order `transactions` was given (callers sort if they need
    chronological order - MwrCalculator does, TwrCalculator buckets by
    period so order doesn't matter to it).
    """
    return [
        (txn.date, EXTERNAL_FLOW_SIGN[txn.type] * flow_magnitude(txn))
        for txn in transactions
        if txn.type in EXTERNAL_FLOW_SIGN
    ]
