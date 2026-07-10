# ADR 0010: Transaction Log as a Validation Layer, Not the Source of Truth for Current Holdings

**Status:** Accepted (implemented in Milestone 4)
**Date:** 2026-07-09

## Decision

The transaction log (`transactions.yaml`, read via `PortfolioRepository`) is used to reconstruct holdings and cash balance for **reconciliation** against the declared state (`holdings.yaml`'s `shares`/`avg_price`, `Portfolio.cash_balance`), which remains authoritative. The engine does not switch to computing live portfolio state from transactions in Milestone 4.

## Reason

Milestone 4's brief asks directly whether the engine should reconstruct holdings from transactions — yes, but *for what purpose* is the real design question. Making the transaction log authoritative would require every portfolio to have a complete, accurate history from account inception to produce correct current state — a much larger requirement than "add a history feature" implies, and one that would silently change what `holdings.yaml` means for anyone not maintaining a full log (i.e., every portfolio that exists today). Treating reconstruction as a validation/diagnostic layer instead delivers the requested capability — the engine genuinely can reconstruct holdings from transactions (`engine/transaction_replay.py`) — without requiring completeness, without changing what any existing file means, and without touching the live data path (`YamlRepository.async_get_portfolios()`'s existing contract, `PortfolioCalculator`, `AllocationCalculator`, `PerformanceCalculator`) at all.

## Alternatives Considered

- **Transactions as the sole source of truth** — derive `Holding.shares`/`avg_price` from the log on every engine run, treating `holdings.yaml`'s own `shares`/`avg_price` fields as vestigial. Rejected: a much bigger, riskier change than the milestone's stated scope, and one that breaks for any portfolio without a complete history — which is every portfolio in current use, since none of them have been logging transactions until now.
- **Dual-mode per portfolio** (some portfolios declared, some derived, selected by a config flag) — rejected for this milestone as unnecessary complexity. Nothing today needs it, and the validation-layer design already provides the useful part (catching drift between declared and actual state) without maintaining two live-data code paths.

## Consequences

- `holdings.yaml`/`cash_balance` remain exactly as important and as trusted as before this milestone — no behavior change for any existing installation, no migration required.
- The reconciliation entity this milestone introduces (`sensor.<portfolio>_reconciliation`) is genuinely new value on top of that: it can catch data-entry mistakes (a typo in `holdings.yaml`, a forgotten manual update after a real-world trade) that were previously undetectable by anything in this system.
- A future milestone could revisit "transactions as source of truth" as an opt-in mode once there's real demand and a migration story for existing portfolios. This ADR doesn't preclude that — it declines to build it now, consistent with the project's standing principle (reaffirmed throughout the governance review) of evolving architecture only when a genuine, demonstrated need arises, not because a more ambitious design can be imagined.
