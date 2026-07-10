from __future__ import annotations

from ..models import Portfolio, Position, TransactionSummary
from .base import Calculator

#: How many recent transactions to surface — matches the entity contract
#: (sensor.<portfolio>_transaction_count's `recent` attribute, Section 9).
RECENT_LIMIT = 10


class TransactionCalculator(Calculator):
    """Summarizes `portfolio.transactions` for the transaction_count entity
    (MILESTONE_4_SPEC.md Section 9) - count plus the most recent entries,
    newest first. No FX/cash-effect computation here; that's
    transaction_replay.py's job (used by ReconciliationCalculator, not
    this one) - this calculator only reports on the log's own shape.
    """

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> TransactionSummary:
        ordered = sorted(portfolio.transactions, key=lambda t: t.date, reverse=True)
        return TransactionSummary(
            count=len(portfolio.transactions),
            recent=ordered[:RECENT_LIMIT],
        )
