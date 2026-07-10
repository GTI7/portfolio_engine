from __future__ import annotations

from ..models import Portfolio, Position, ReconciliationDiscrepancy, ReconciliationResult
from ..transaction_replay import replay_transactions
from .base import Calculator

#: Below this absolute difference, a discrepancy is treated as float/
#: rounding noise, not a real mismatch worth surfacing. Chosen as a fixed
#: small monetary/share amount rather than a percentage - a percentage
#: tolerance would let large positions hide large absolute discrepancies,
#: which is exactly the kind of thing this calculator exists to catch.
TOLERANCE = 0.01


class ReconciliationCalculator(Calculator):
    """Compares declared portfolio state (`portfolio.holdings`,
    `portfolio.cash_balance`) against what `portfolio.transactions` implies
    via `transaction_replay.replay_transactions`. A data-integrity check,
    not a portfolio metric - see MILESTONE_4_SPEC.md Section 6.2 and
    docs/adr/0010-transaction-log-as-validation-layer.md.

    Only compares shares, avg_price, and cash_balance - never `type` or
    `currency`, since the transaction log has no way to assert either of
    those (see transaction_replay.py's note on reconstructed Holding.type
    always being "stock") and flagging a field the log can't actually
    speak to would be a false positive by construction, not a real
    discrepancy.
    """

    def calculate(self, portfolio: Portfolio, positions: list[Position]) -> ReconciliationResult:
        if not portfolio.transactions:
            return ReconciliationResult(status="no_data", transactions_considered=0)

        replay = replay_transactions(portfolio.transactions)
        discrepancies: list[ReconciliationDiscrepancy] = []

        # O(1) lookup per symbol below, instead of scanning `positions`
        # linearly inside the loop (which would make this calculator O(n^2)
        # in portfolio size — caught by scripts/benchmark.py showing
        # super-linear scaling at 500/1000 holdings before this fix).
        declared_by_symbol = {p.holding.symbol: p.holding for p in positions}
        declared_symbols = set(declared_by_symbol.keys())
        reconstructed_symbols = set(replay.holdings.keys())

        for symbol in sorted(declared_symbols | reconstructed_symbols):
            declared = declared_by_symbol.get(symbol)
            reconstructed = replay.holdings.get(symbol)

            declared_shares = declared.shares if declared else 0.0
            reconstructed_shares = reconstructed.shares if reconstructed else 0.0
            _compare(discrepancies, symbol, "shares", declared_shares, reconstructed_shares)

            # avg_price is only meaningful to compare when both sides
            # actually hold the symbol - comparing cost basis on a symbol
            # one side doesn't hold at all is not a meaningful discrepancy
            # on top of the shares one already reported above.
            if declared and reconstructed:
                _compare(
                    discrepancies, symbol, "avg_price", declared.avg_price, reconstructed.avg_price
                )

        _compare(discrepancies, None, "cash_balance", portfolio.cash_balance, replay.cash_balance)

        status = "discrepancy" if discrepancies else "ok"
        return ReconciliationResult(
            status=status,
            discrepancies=discrepancies,
            transactions_considered=len(portfolio.transactions),
        )


def _compare(
    discrepancies: list[ReconciliationDiscrepancy],
    symbol: str | None,
    field: str,
    declared: float,
    reconstructed: float,
) -> None:
    difference = declared - reconstructed
    if abs(difference) > TOLERANCE:
        discrepancies.append(
            ReconciliationDiscrepancy(
                symbol=symbol,
                field=field,
                declared=round(declared, 6),
                reconstructed=round(reconstructed, 6),
                difference=round(difference, 6),
            )
        )
