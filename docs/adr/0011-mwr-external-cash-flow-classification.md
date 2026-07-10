# ADR 0011: External Cash Flow Classification for Money-Weighted Return

**Status:** Accepted
**Date:** 2026-07-09

## Decision

`MwrCalculator` builds its XIRR cash-flow series from `portfolio.transactions` using this classification:

| Transaction type | Counted as external cash flow? | Sign / magnitude |
|---|---|---|
| `DEPOSIT` | Yes | negative, `amount` |
| `WITHDRAWAL` | Yes | positive, `amount` |
| `TRANSFER_IN` | Yes | negative, `shares * price` (in-kind contribution) |
| `TRANSFER_OUT` | Yes | positive, `shares * price` (in-kind withdrawal) |
| `BUY`, `SELL`, `DIVIDEND`, `FEE` | No | — |

Plus one terminal cash flow: the portfolio's current total value (`PortfolioSummary.total_value` — positions plus cash), positive, dated "now" (or an injected `as_of` for deterministic testing).

## Reason

Money-weighted return measures the return on capital the investor actually put at risk — it needs exactly the cash flows that cross the boundary between "the investor's money" and "the portfolio," not every transaction in the log. `BUY`/`SELL` move value between cash and positions *within* the portfolio — no capital crosses the boundary, so including them would double-count: a `BUY` already shows up in the terminal value as a position, and treating it as an external outflow too would make MWR reflect nothing meaningful. `DIVIDEND` and `FEE` are cash movements *within* the portfolio's own cash balance (Milestone 1's cash-as-first-class design, ADR-0008) — a dividend that's never withdrawn is already sitting in `cash_balance`, which the terminal value already includes; counting it as an external inflow as well would double-count it a second time. `TRANSFER_IN`/`TRANSFER_OUT` are the one case that genuinely needs special handling: they move shares without a matching internal cash transaction (`Transaction.amount` is required to be exactly `0.0` for these two types — Milestone 4), but from the investor's perspective an in-kind transfer is economically identical to a cash contribution/withdrawal of that value. Treating their cash effect as `0.0` (matching the literal `Transaction.amount`) would silently misattribute a $10,000 in-kind transfer as if the portfolio had organically grown by $10,000 through investment performance.

## Alternatives Considered

- **Treat every transaction with a non-zero cash effect as an external flow** (i.e., reuse `CASH_EFFECT_SIGN` directly) — rejected. This is exactly the double-counting trap described above: `BUY`/`SELL`/`DIVIDEND`/`FEE` all have real, non-zero cash effects, but those effects are *internal* to the portfolio and already captured in the terminal value.
- **Ignore `TRANSFER_IN`/`TRANSFER_OUT` entirely** (since their literal `amount` is `0.0`) — rejected for the reason above: it would let in-kind transfers masquerade as investment performance, which is precisely the kind of distortion MWR exists to avoid.
- **Include `DIVIDEND` as an external inflow** (treating it as if distributed to the investor, common in some MWR conventions for funds that always distribute) — rejected for this project specifically, since `Portfolio.cash_balance` already models dividends as retained-by-default (ADR-0008); a user who actually withdraws dividend income records that as a separate `WITHDRAWAL`, which is already correctly counted.

## Consequences

- MWR is only as accurate as the transaction log's completeness for `DEPOSIT`/`WITHDRAWAL`/`TRANSFER_IN`/`TRANSFER_OUT` entries specifically — a log with accurate `BUY`/`SELL` history but a missing `DEPOSIT` will understate contributed capital and produce a misleadingly high return. This is the same class of limitation already documented for reconciliation (MILESTONE_4_SPEC.md Section 15) and isn't a new risk this milestone introduces, just a second consumer of the same underlying data-completeness assumption.
- A portfolio with only `BUY`/`SELL`/`DIVIDEND` transactions and no `DEPOSIT`/`WITHDRAWAL`/`TRANSFER_IN`/`TRANSFER_OUT` at all has zero external cash flows — `MwrCalculator` reports `status: "no_data"` rather than attempting a calculation with only the terminal value (which `engine/xirr.py` would correctly reject anyway, since a single positive flow has no sign change to solve against).
- If a future milestone changes how dividends are modeled (e.g., an explicit "distributed vs. reinvested" flag), this classification table is the one place to revisit — nothing about `MwrCalculator`'s structure or `engine/xirr.py` would need to change, only which transaction types map to which cash-flow treatment.
