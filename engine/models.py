"""Domain model for the Portfolio Engine.

Deliberately HA-independent: no `homeassistant.*` imports anywhere in this
package. That's what keeps `engine/` unit-testable with plain pytest and
reusable outside Home Assistant if that's ever useful.

Per ADR-0004, this module only defines the models each milestone actually
uses. `Dividend`, `Goal`, `Account`, and `Benchmark` remain future additions
(architecture doc); `Transaction` was added in Milestone 4 — see
MILESTONE_4_SPEC.md and docs/adr/0010-transaction-log-as-validation-layer.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


@dataclass
class Quote:
    """A single point-in-time market data point for one symbol."""

    symbol: str
    price: float
    currency: str
    change_pct: float = 0.0
    name: str | None = None
    as_of: datetime | None = None


@dataclass
class Holding:
    """Pure user-entered configuration. Maps 1:1 to a holdings.yaml entry.

    No calculated fields belong here — see ADR context in the architecture
    doc's Layer 1 discussion. This is intentionally a thin, flat shape.
    """

    symbol: str
    shares: float
    avg_price: float
    currency: str
    type: str
    account: str | None = None

    def __post_init__(self) -> None:
        if self.shares < 0:
            raise ValueError(f"{self.symbol}: shares cannot be negative")
        if self.avg_price < 0:
            raise ValueError(f"{self.symbol}: avg_price cannot be negative")
        if not self.currency:
            raise ValueError(f"{self.symbol}: currency is required")
        if not self.type:
            raise ValueError(f"{self.symbol}: type is required")


@dataclass
class Position:
    """A Holding combined with a live Quote — engine output, never persisted
    as config.

    `market_value`/`cost_basis` are in the holding's own currency;
    `market_value_base`/`cost_basis_base` are converted to the portfolio's
    base currency via the FX rate supplied to the engine (Milestone 3 —
    see providers/currency_base.py). `unrealized_gain`/`gain_pct` are
    computed on the base-currency figures, since "how much did I gain"
    should mean gain in the currency the investor actually thinks in, not a
    same-units-only comparison that's meaningless once currencies differ.
    For a holding whose currency already equals the portfolio's base
    currency, `fx_rate` is 1.0 and every base-currency field is numerically
    identical to its native-currency counterpart — this is what keeps
    Milestone 1/2 behavior unchanged for single-currency portfolios.
    """

    holding: Holding
    quote: Quote | None
    market_value: float
    market_value_base: float
    cost_basis: float
    cost_basis_base: float
    unrealized_gain: float
    gain_pct: float
    day_change_pct: float
    fx_rate: float = 1.0

    @property
    def symbol(self) -> str:
        return self.holding.symbol


class TransactionType(Enum):
    """Per MILESTONE_4_SPEC.md Section 4.1 — exactly the set the milestone
    named, no additions. Sign semantics (which types increase vs. decrease
    cash) live entirely here, not on Transaction.amount — see
    Transaction's docstring and CASH_EFFECT_SIGN below.
    """

    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    FEE = "fee"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


#: The sign to apply to Transaction.amount (always an unsigned magnitude)
#: to get this type's effect on cash balance. TRANSFER_IN/TRANSFER_OUT are
#: 0 because shares move without any cash changing hands - amount is
#: required to be exactly 0.0 for those two types (see Transaction
#: validation), so the sign is moot for them, but included here for
#: completeness and so transaction_replay.py has one table to consult
#: rather than re-deriving this per type.
CASH_EFFECT_SIGN: dict[TransactionType, int] = {
    TransactionType.BUY: -1,
    TransactionType.WITHDRAWAL: -1,
    TransactionType.FEE: -1,
    TransactionType.SELL: 1,
    TransactionType.DEPOSIT: 1,
    TransactionType.DIVIDEND: 1,
    TransactionType.TRANSFER_IN: 0,
    TransactionType.TRANSFER_OUT: 0,
}

#: Types that represent a position change (shares moving), as opposed to a
#: pure cash event. Used by both validation (which types require
#: symbol/shares/price) and transaction_replay.py (which types affect
#: holdings vs. only cash).
_POSITION_TYPES = frozenset(
    {
        TransactionType.BUY,
        TransactionType.SELL,
        TransactionType.TRANSFER_IN,
        TransactionType.TRANSFER_OUT,
    }
)

#: Of the position types, which one is a "buy-like" addition to the
#: position (increases shares, contributes a new cost-basis lot) vs. a
#: "sell-like" reduction (decreases shares, cost basis unchanged).
_INCREASES_SHARES = frozenset({TransactionType.BUY, TransactionType.TRANSFER_IN})
_DECREASES_SHARES = frozenset({TransactionType.SELL, TransactionType.TRANSFER_OUT})


@dataclass
class Transaction:
    """One immutable, append-only ledger entry. See MILESTONE_4_SPEC.md
    Section 4.2 for the full design rationale, in particular why `amount`
    is an unsigned magnitude rather than a signed cash-flow value: encoding
    direction in both `type` and the sign of `amount` allows the two to
    disagree (`{type: BUY, amount: +1000}` would be nonsensical but
    schema-valid); making `amount` unsigned removes that class of invalid
    data entirely - `type` alone determines direction (CASH_EFFECT_SIGN
    above), applied in exactly one place (transaction_replay.py).

    Immutability is a convention this class doesn't (and can't, in Python)
    enforce mechanically - correcting a mistake means appending a new
    transaction referencing the original in `notes`, not editing this one
    in place. Nothing about the dataclass itself prevents mutation; the
    discipline lives in how callers are expected to use it (repository
    reads never construct-then-mutate, and no code path in this project
    does either).
    """

    id: str
    portfolio_id: str
    type: TransactionType
    date: datetime
    currency: str
    amount: float
    symbol: str | None = None
    shares: float | None = None
    price: float | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Transaction: id is required")
        if not self.portfolio_id:
            raise ValueError(f"{self.id}: portfolio_id is required")
        if not self.currency:
            raise ValueError(f"{self.id}: currency is required")
        if not isinstance(self.date, datetime):
            raise ValueError(f"{self.id}: date must be a datetime")

        # amount: always an unsigned magnitude (see class docstring); exactly
        # zero for the two transfer types (no cash moves), positive for
        # everything else.
        if self.amount < 0:
            raise ValueError(
                f"{self.id}: amount cannot be negative (it's a magnitude, not a signed cash flow)"
            )
        if self.type in (TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT):
            if self.amount != 0.0:
                raise ValueError(
                    f"{self.id}: {self.type.value} must have amount == 0.0 "
                    "(no cash moves in a transfer)"
                )
        else:
            if self.amount <= 0:
                raise ValueError(f"{self.id}: {self.type.value} requires amount > 0")

        # symbol/shares/price presence rules per MILESTONE_4_SPEC.md Section 8.
        if self.type in _POSITION_TYPES:
            if not self.symbol:
                raise ValueError(f"{self.id}: {self.type.value} requires symbol")
            if self.shares is None or self.shares <= 0:
                raise ValueError(f"{self.id}: {self.type.value} requires shares > 0")
            if self.price is None or self.price <= 0:
                raise ValueError(f"{self.id}: {self.type.value} requires price > 0")
        else:
            if self.symbol is not None and self.type is not TransactionType.DIVIDEND:
                raise ValueError(f"{self.id}: {self.type.value} must not have a symbol")
            if self.type is TransactionType.DIVIDEND and not self.symbol:
                raise ValueError(f"{self.id}: dividend requires symbol")
            if self.shares is not None:
                raise ValueError(f"{self.id}: {self.type.value} must not have shares")
            if self.price is not None:
                raise ValueError(f"{self.id}: {self.type.value} must not have price")


@dataclass
class Portfolio:
    """A named collection of holdings. Multi-portfolio support (aggregation
    across portfolios) is deferred to a later milestone; this shape already
    supports it without changes when that lands.

    `cash_balance` is a first-class field (not a special case bolted onto
    calculators) so allocation, total value, goals, and future snapshots all
    see cash the same way they see any other position — see
    docs/adr/0008-cash-as-first-class-domain-concept.md.

    `transactions` (Milestone 4) is additive and defaults to empty — every
    pre-Milestone-4 `Portfolio(...)` construction continues to work
    unmodified. It's a historical/validation record, not the source of
    truth for `holdings`/`cash_balance` above — see
    docs/adr/0010-transaction-log-as-validation-layer.md. Populating it is
    what lets ReconciliationCalculator/TransactionCalculator (both read via
    the unchanged `Calculator.calculate(portfolio, positions)` interface)
    do their work without any change to that interface.

    `snapshots` (Milestone 6) is the same pattern again, one field further:
    additive, defaults to empty, comes from a *separate* SnapshotRepository
    (not PortfolioRepository) and is attached to the Portfolio object by
    the caller (update_logic.py) after both repositories have been read -
    see docs/adr/0012-snapshot-repository-and-store-backed-persistence.md.
    This is what lets TwrCalculator read `portfolio.snapshots` through the
    same unchanged `Calculator.calculate(portfolio, positions)` interface
    every other calculator uses.
    """

    id: str
    name: str
    holdings: list[Holding] = field(default_factory=list)
    base_currency: str = "EUR"
    cash_balance: float = 0.0
    transactions: list[Transaction] = field(default_factory=list)
    snapshots: list[Snapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cash_balance < 0:
            raise ValueError(f"{self.id}: cash_balance cannot be negative")


@dataclass
class PortfolioSummary:
    """Output of PortfolioCalculator.

    `total_positions_value` (holdings only) and `total_value` (holdings +
    cash) are both exposed because they answer different questions: ROI is
    meaningful only against invested capital (cash sitting uninvested didn't
    gain or lose anything), while "how much am I worth" needs cash included.
    """

    total_positions_value: float
    cash_balance: float
    total_value: float
    total_invested: float
    total_unrealized_gain: float
    roi_pct: float


@dataclass
class AllocationGroup:
    label: str
    value: float
    pct: float


@dataclass
class PerformanceResult:
    """Output of PerformanceCalculator. Day-change is fully computed today;
    weekly/monthly/YTD are stubbed at 0.0 until Milestone 7's history layer
    (snapshots) exists to compute them from — see ADR-0003. Stubbing these
    as explicit, documented zeros (not omitting the fields) keeps the shape
    stable for dashboards that will bind to them later.
    """

    day_change_pct: float
    weekly_change_pct: float = 0.0
    monthly_change_pct: float = 0.0
    ytd_change_pct: float = 0.0


@dataclass
class ReconciliationDiscrepancy:
    """One field where declared state (holdings.yaml/cash_balance) and the
    transaction log's reconstruction disagree beyond tolerance.
    """

    symbol: str | None   # None for the cash-balance discrepancy
    field: str            # "shares" | "avg_price" | "cash_balance"
    declared: float
    reconstructed: float
    difference: float


@dataclass
class ReconciliationResult:
    """Output of ReconciliationCalculator. `status` is deliberately a
    three-way value, not a bool: "no_data" (no transactions to compare
    against) is not the same claim as "ok" (compared and matched) - see
    docs/adr/0010-transaction-log-as-validation-layer.md.
    """

    status: str   # "ok" | "discrepancy" | "no_data"
    discrepancies: list[ReconciliationDiscrepancy] = field(default_factory=list)
    transactions_considered: int = 0


@dataclass
class TransactionSummary:
    """Output of TransactionCalculator."""

    count: int
    recent: list[Transaction] = field(default_factory=list)


@dataclass
class MwrResult:
    """Output of MwrCalculator. `status` mirrors ReconciliationResult's
    three-way pattern for the same reason: "not computable" is not the
    same claim as "computed and it's exactly 0%" - collapsing them into a
    bare float (or float | None with no explanation) would lose exactly
    the information a dashboard or automation needs to distinguish "no
    return data yet" from "a genuine 0% return."
    """

    status: str   # "ok" | "no_data" | "insufficient_data" | "not_computable"
    rate_pct: float | None = None
    cash_flow_count: int = 0
    as_of: datetime | None = None


@dataclass
class HoldingSnapshot:
    """One symbol's contribution to a Snapshot's holdings summary - deliberately
    minimal (symbol, shares, current base-currency value only). Cost basis
    history is the transaction log's job (Milestone 4), not the snapshot's -
    a snapshot answers "what was this worth then," not "what was paid for it."
    """

    symbol: str
    shares: float
    market_value_base: float

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("HoldingSnapshot: symbol is required")
        if self.shares < 0:
            raise ValueError(f"{self.symbol}: shares cannot be negative")
        if self.market_value_base < 0:
            raise ValueError(f"{self.symbol}: market_value_base cannot be negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "shares": self.shares,
            "market_value_base": self.market_value_base,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> HoldingSnapshot:
        return cls(
            symbol=str(data["symbol"]),
            shares=float(data["shares"]),  # type: ignore[arg-type]
            market_value_base=float(data["market_value_base"]),  # type: ignore[arg-type]
        )


@dataclass
class Snapshot:
    """An immutable, point-in-time record of a portfolio's total value,
    cash balance, invested capital, and holdings summary - the missing
    prerequisite for time-weighted return (Milestone 6) that
    MILESTONE_4_SPEC.md Section 11 identified back in Milestone 4.

    Immutable by the same convention as Transaction (Milestone 4): never
    mutated after creation, append-only in whatever repository stores it.
    `to_dict`/`from_dict` exist directly on this model (unlike Transaction,
    whose serialization lives in the repository layer) because Snapshot's
    primary storage target is Home Assistant's `Store` helper - a JSON-
    native persistence mechanism, not a YAML file a human might hand-edit -
    so a single, model-owned serialization contract is the right place for
    it rather than duplicating (date, enum) handling in every repository
    implementation. See docs/adr/0012-snapshot-repository-and-store-backed-persistence.md.
    """

    id: str
    portfolio_id: str
    timestamp: datetime
    portfolio_value: float
    cash_balance: float
    invested: float
    base_currency: str
    holdings: list[HoldingSnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Snapshot: id is required")
        if not self.portfolio_id:
            raise ValueError(f"{self.id}: portfolio_id is required")
        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"{self.id}: timestamp must be a datetime")
        if self.portfolio_value < 0:
            raise ValueError(f"{self.id}: portfolio_value cannot be negative")
        if self.cash_balance < 0:
            raise ValueError(f"{self.id}: cash_balance cannot be negative")
        if self.invested < 0:
            raise ValueError(f"{self.id}: invested cannot be negative")
        if not self.base_currency:
            raise ValueError(f"{self.id}: base_currency is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "timestamp": self.timestamp.isoformat(),
            "portfolio_value": self.portfolio_value,
            "cash_balance": self.cash_balance,
            "invested": self.invested,
            "base_currency": self.base_currency,
            "holdings": [h.to_dict() for h in self.holdings],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Snapshot:
        """Tolerant of a missing `holdings` key (defaults to empty) so an
        older-schema snapshot (a field added in a later milestone without
        one here) still loads rather than failing outright - "migration
        safety" per MILESTONE_6 Phase 2's own test requirement. Required
        fields are still required; this isn't a blanket try/except, only a
        deliberate default for genuinely optional/additive fields.
        """
        raw_timestamp = data["timestamp"]
        timestamp = (
            datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
            if isinstance(raw_timestamp, str)
            else raw_timestamp
        )
        holdings_data = data.get("holdings") or []
        return cls(
            id=str(data["id"]),
            portfolio_id=str(data["portfolio_id"]),
            timestamp=timestamp,  # type: ignore[arg-type]
            portfolio_value=float(data["portfolio_value"]),  # type: ignore[arg-type]
            cash_balance=float(data["cash_balance"]),  # type: ignore[arg-type]
            invested=float(data["invested"]),  # type: ignore[arg-type]
            base_currency=str(data["base_currency"]),
            holdings=[HoldingSnapshot.from_dict(h) for h in holdings_data],  # type: ignore[attr-defined]
        )


@dataclass
class TwrResult:
    """Output of TwrCalculator. Same three-way-plus-ok `status` pattern as
    MwrResult/ReconciliationResult. `twr_pct` is the CUMULATIVE (holding-
    period) time-weighted return over the observed period - from the
    earliest available Snapshot to `as_of` - not annualized. Annualizing
    was explicitly deferred at Milestone 6 (see `annualized_pct` below,
    added Milestone 7) rather than baked into `twr_pct` itself, so this
    field's meaning was never at risk of changing later.
    """

    status: str   # "ok" | "no_data" | "insufficient_data" | "not_computable"
    twr_pct: float | None = None
    annualized_pct: float | None = None
    periods_used: int = 0
    as_of: datetime | None = None


@dataclass
class DividendResult:
    """Output of DividendCalculator. Rolling-12-month is the state's own
    figure (see docs/ENTITY_CONTRACTS.md's dividend_income entry) - the
    rest are attributes, per MILESTONE_7's "one entity, rich attributes"
    scope decision.
    """

    status: str   # "ok" | "no_data"
    rolling_12_months: float = 0.0
    current_year: float = 0.0
    lifetime: float = 0.0
    dividend_yield_pct: float | None = None
    average_monthly_dividend: float = 0.0
    as_of: datetime | None = None


@dataclass
class DrawdownResult:
    """Output of DrawdownCalculator. Unlike MwrResult/TwrResult,
    "insufficient_data" doesn't apply here - a single data point is
    already enough to compute a (trivially "at peak") drawdown, since
    drawdown doesn't need a *return* between two points the way MWR/TWR
    do, just a value and a running peak to compare it against.
    """

    status: str   # "ok" | "no_data"
    current_drawdown_pct: float = 0.0
    maximum_drawdown_pct: float = 0.0
    peak_value: float | None = None
    peak_date: datetime | None = None
    recovery_status: str | None = None   # "at_peak" | "recovering" | "in_drawdown"
    as_of: datetime | None = None


@dataclass
class VolatilityResult:
    """Output of VolatilityCalculator."""

    status: str   # "ok" | "no_data" | "insufficient_data" | "not_computable"
    daily_volatility_pct: float | None = None
    annualized_volatility_pct: float | None = None
    observation_period_days: int = 0
    sample_count: int = 0
    as_of: datetime | None = None


@dataclass
class PositionSummary:
    symbol: str
    pct_of_portfolio: float
    gain_pct: float


@dataclass
class PositionAnalyticsResult:
    """Output of PositionAnalyticsCalculator."""

    status: str   # "ok" | "no_data"
    largest_position: PositionSummary | None = None
    largest_winner: PositionSummary | None = None
    largest_loser: PositionSummary | None = None
    top5_concentration_pct: float = 0.0
    diversification_score: float = 0.0   # 0 (fully concentrated) - 100 (perfectly diversified)
    herfindahl_index: float = 0.0
    holding_count: int = 0
