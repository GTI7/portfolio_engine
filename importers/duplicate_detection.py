"""Duplicate detection for imported transactions against a portfolio's
existing transaction log. Two independent checks - see
docs/adr/0013-broker-import-transaction-id-reuse.md for why both are
needed rather than one subsuming the other.
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.models import Transaction

#: Shares/amount are compared with a small absolute tolerance to avoid
#: floating-point representation differences between a broker's own export
#: and however the existing log stored the same number causing a false
#: negative (same convention as ReconciliationCalculator's TOLERANCE).
HEURISTIC_TOLERANCE = 0.01


@dataclass
class DuplicateMatch:
    imported: Transaction
    matched_existing_id: str
    reason: str  # "id" | "heuristic"


def detect_duplicates(
    imported: list[Transaction], existing: list[Transaction]
) -> list[DuplicateMatch]:
    existing_by_id = {t.id: t for t in existing}
    matches: list[DuplicateMatch] = []

    for txn in imported:
        if txn.id in existing_by_id:
            matches.append(
                DuplicateMatch(imported=txn, matched_existing_id=txn.id, reason="id")
            )
            continue

        heuristic_match = _find_heuristic_match(txn, existing)
        if heuristic_match is not None:
            matches.append(
                DuplicateMatch(
                    imported=txn, matched_existing_id=heuristic_match.id, reason="heuristic"
                )
            )

    return matches


def _find_heuristic_match(txn: Transaction, existing: list[Transaction]) -> Transaction | None:
    for candidate in existing:
        if candidate.type != txn.type:
            continue
        if candidate.date != txn.date:
            continue
        if candidate.symbol != txn.symbol:
            continue
        if not _close(candidate.shares, txn.shares):
            continue
        if not _close(candidate.amount, txn.amount):
            continue
        return candidate
    return None


def _close(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= HEURISTIC_TOLERANCE
