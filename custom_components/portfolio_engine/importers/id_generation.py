"""Deterministic id generation for broker export rows that have no native
reference of their own (e.g. a Generic CSV row with no id column) - see
docs/adr/0013-broker-import-transaction-id-reuse.md for why this must be
deterministic (a hash of the row's content) rather than a random UUID.
"""
from __future__ import annotations

import hashlib


def deterministic_transaction_id(
    type_: str,
    date_iso: str,
    symbol: str | None,
    shares: float | None,
    amount: float,
    currency: str,
) -> str:
    """Same inputs always produce the same id - re-parsing the same file
    twice must yield the same generated id for the same row, so exact-id
    duplicate detection can catch a re-import of an unchanged file even
    when the source format has no native transaction reference.
    """
    key = (
        f"{type_}|{date_iso}|{symbol or ''}|"
        f"{shares if shares is not None else ''}|{amount}|{currency}"
    )
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"gen-{digest}"
