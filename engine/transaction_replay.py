"""Replays a transaction log into reconstructed holdings and cash balance.

Deliberately NOT a Calculator (see MILESTONE_4_SPEC.md Section 6.1):
replaying an event log into current state is a different kind of transform
than "aggregate already-known positions into insights," which is what the
Calculator interface (`calculate(portfolio, positions)`) is shaped for.
ReconciliationCalculator calls into this module internally; this module
itself has no dependency on Calculator at all.

HA-independent, no new external dependencies - same as every other module
under engine/.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    _DECREASES_SHARES,
    _INCREASES_SHARES,
    CASH_EFFECT_SIGN,
    Holding,
    Transaction,
)


@dataclass
class TransactionReplayResult:
    """Bundled so future fields (realized gains, per-symbol statistics)
    are additive to this shape rather than new parallel return values
    every caller has to learn about (see MILESTONE_4_SPEC.md Section 6.1,
    revised after review). `warnings` was added during implementation
    (not speculatively) - see replay_transactions's docstring on oversold
    positions, a real case discovered while writing this module, not a
    pre-imagined "might need it later" field.
    """

    holdings: dict[str, Holding]
    cash_balance: float
    warnings: list[str] = field(default_factory=list)


class _Accumulator:
    """Mutable, unvalidated running total for one symbol during replay.
    Deliberately NOT a Holding - Holding.__post_init__ forbids negative
    shares, which is the correct rule for user-declared config
    (holdings.yaml) but wrong here: an incomplete or inconsistent
    transaction log can legitimately imply a negative running position
    mid-replay (e.g. a SELL recorded before its matching BUY, or a log that
    doesn't start from account inception), and rejecting that outright
    would defeat the entire purpose of reconciliation - the discrepancy
    needs to surface, not raise. Only the final, clamped result is turned
    into a real Holding.
    """

    __slots__ = ("shares", "avg_price", "currency", "type", "account")

    def __init__(
        self,
        shares: float,
        avg_price: float,
        currency: str,
        type_: str,
        account: str | None,
    ):
        self.shares = shares
        self.avg_price = avg_price
        self.currency = currency
        self.type = type_
        self.account = account


def replay_transactions(
    transactions: list[Transaction], opening_cash_balance: float = 0.0
) -> TransactionReplayResult:
    """Replay a transaction log, in `date` order (id is not a sort key),
    into reconstructed holdings and cash balance.

    Holdings use weighted-average cost basis - the same method
    `Holding.avg_price` already represents everywhere else in this project,
    not FIFO/LIFO lots:
      BUY / TRANSFER_IN: shares += qty; avg_price recomputed as the
        weighted average of the existing position and the new lot.
      SELL / TRANSFER_OUT: shares -= qty; avg_price UNCHANGED - weighted-
        average cost basis doesn't move on a sale. This module does not
        compute or expose realized gains (see MILESTONE_4_SPEC.md
        Non-Goals).
      DIVIDEND / DEPOSIT / WITHDRAWAL / FEE: no effect on holdings.

    Cash balance starts at `opening_cash_balance` and accumulates each
    transaction's signed effect via TransactionType's CASH_EFFECT_SIGN
    table (engine/models.py) - `type` alone determines direction; `amount`
    is always the unsigned magnitude (Transaction's own validation
    guarantees this, so no sign-consistency check is needed here).

    A log that doesn't start from account inception will not reconcile
    exactly against the true current cash balance/holdings unless an
    opening balance (and, for holdings, an opening TRANSFER_IN per
    pre-existing position) is supplied - a documented limitation
    (MILESTONE_4_SPEC.md Section 15), not something this function can fix.

    A SELL/TRANSFER_OUT for more shares than currently held (per this
    replay) does not raise. Doing so would require this function to assume
    the log is complete and correctly ordered relative to the *true*
    history - exactly the assumption ADR-0010 declines to make. Instead,
    the final reconstructed share count is clamped to 0 (a real Holding
    cannot have negative shares - see _Accumulator's docstring) and a
    human-readable entry is appended to `TransactionReplayResult.warnings`,
    so the caller (ReconciliationCalculator) can surface it as a
    discrepancy rather than the replay either crashing or silently losing
    the information.
    """
    ordered = sorted(transactions, key=lambda t: t.date)

    accumulators: dict[str, _Accumulator] = {}
    cash_balance = opening_cash_balance
    warnings: list[str] = []

    for txn in ordered:
        cash_balance += CASH_EFFECT_SIGN[txn.type] * txn.amount

        if txn.type in _INCREASES_SHARES:
            _apply_increase(accumulators, txn)
        elif txn.type in _DECREASES_SHARES:
            _apply_decrease(accumulators, txn)
        # DIVIDEND / DEPOSIT / WITHDRAWAL / FEE: no effect on holdings.

    holdings: dict[str, Holding] = {}
    for symbol, acc in accumulators.items():
        shares = acc.shares
        if shares < 0:
            warnings.append(
                f"{symbol}: reconstructed shares went negative ({shares:g}) - the "
                "transaction log implies more shares were sold/transferred out than "
                "were ever bought/transferred in. Clamped to 0 for this result; "
                "likely an incomplete log (missing an opening TRANSFER_IN) or an "
                "out-of-order/incorrect entry."
            )
            shares = 0.0
        holdings[symbol] = Holding(
            symbol=symbol,
            shares=shares,
            avg_price=round(acc.avg_price, 6),
            currency=acc.currency,
            type=acc.type,
            account=acc.account,
        )

    return TransactionReplayResult(
        holdings=holdings, cash_balance=round(cash_balance, 2), warnings=warnings
    )


def _apply_increase(accumulators: dict[str, _Accumulator], txn: Transaction) -> None:
    """BUY or TRANSFER_IN: add a new lot, recompute weighted-average cost basis."""
    assert txn.symbol is not None and txn.shares is not None and txn.price is not None

    existing = accumulators.get(txn.symbol)
    if existing is None:
        accumulators[txn.symbol] = _Accumulator(
            shares=txn.shares,
            avg_price=txn.price,
            currency=txn.currency,
            type_="stock",  # the transaction log doesn't carry asset type - see note below
            account=None,
        )
        return

    new_shares = existing.shares + txn.shares
    if new_shares != 0:
        existing.avg_price = (
            (existing.shares * existing.avg_price) + (txn.shares * txn.price)
        ) / new_shares
    existing.shares = new_shares


def _apply_decrease(accumulators: dict[str, _Accumulator], txn: Transaction) -> None:
    """SELL or TRANSFER_OUT: reduce shares, cost basis (avg_price) unchanged."""
    assert txn.symbol is not None and txn.shares is not None

    existing = accumulators.get(txn.symbol)
    if existing is None:
        # Selling something never bought in this log - allowed; goes
        # negative and is clamped/warned about in replay_transactions.
        accumulators[txn.symbol] = _Accumulator(
            shares=-txn.shares,
            avg_price=txn.price or 0.0,
            currency=txn.currency,
            type_="stock",
            account=None,
        )
        return

    existing.shares -= txn.shares
