# Troubleshooting

## The integration won't set up / shows an error immediately

The most common cause is the investments folder path not existing. It must exist (even if empty) relative to your Home Assistant config directory — an error here tells you this immediately at setup time rather than leaving you with a broken integration to debug later. Fix the path in Settings → Devices & Services → Portfolio Engine → ⋮ → Reconfigure (if available for your version) or remove and re-add the integration with the corrected path.

## No entities showing up at all

You have the integration configured, but no portfolio subfolders exist yet (or none contain a valid `holdings.yaml`). See [Getting Started](GETTING_STARTED.md) — create at least one portfolio subfolder with a `holdings.yaml` inside it, then reload the integration.

## A specific entity shows "unknown"

This is normal for several entities until enough data exists, and is not itself a bug:
- **Money-Weighted Return** — needs `transactions.yaml` with at least one `deposit`/`withdrawal`/`transfer_in`/`transfer_out` entry.
- **Time-Weighted Return, Drawdown, Volatility** — need snapshot history, which accumulates automatically at one snapshot per calendar day. On a brand-new portfolio, these stay `unknown` for the first day or two.
- **Dividend Income** — needs at least one `dividend` transaction in `transactions.yaml`.

Check the entity's own attributes (in Developer Tools → States, or the entity's more-info dialog) — every one of these has a `status` attribute (`no_data`, `insufficient_data`, or `not_computable`) explaining specifically why.

## Repair issues

Portfolio Engine uses Home Assistant's Repairs framework (Settings → System → Repairs, or the notification bell) for problems worth your attention. Each one clears itself automatically once the underlying condition is resolved — you don't need to dismiss them manually, though you can.

- **"Invalid transaction or holdings data"** — your `transactions.yaml` or `holdings.yaml` has something Portfolio Engine can't parse: a typo, a missing required field, or an invalid value (e.g. negative shares). The issue's description includes the specific error. Fix the file and reload the integration.
- **"Reconciliation discrepancy"** — your declared `holdings.yaml`/cash balance doesn't match what your `transactions.yaml` log implies. This is a data-integrity check, not an error in your portfolio's value — your other numbers are unaffected. Usually means a real-world trade was recorded in one file but not the other; check the Reconciliation entity's `discrepancies` attribute for exactly which symbol/field is off and by how much.
- **"Missing exchange rates"** — a foreign-currency holding's exchange rate couldn't be fetched this refresh. Affected positions temporarily use a 1:1 fallback rate. Usually resolves itself within a few update cycles (a provider hiccup, not something you need to fix).
- **"Snapshot storage unavailable"** — Home Assistant couldn't read or write your portfolio's snapshot history. Prices and current value are unaffected; only historical metrics (TWR, drawdown, volatility) may be stale until this resolves. Usually indicates a Home Assistant storage problem — check available disk space and the Home Assistant logs.

## Getting more detail for a bug report

Settings → Devices & Services → Portfolio Engine → ⋮ → **Download Diagnostics**. This produces a file with repository/provider identity, the active calculator list, engine and Home Assistant version info, snapshot and transaction statistics, and a snapshot of every metric's current value and status — everything needed to diagnose an issue without you having to describe your whole setup by hand. It does not include your actual holdings, transaction amounts, or file paths (those are redacted or simply not included) — safe to attach to a bug report.

## Prices or exchange rates seem stale

Portfolio Engine only refreshes on its configured update interval (15 minutes by default). If you need fresher data sooner, Settings → Devices & Services → Portfolio Engine → ⋮ → Reload triggers an immediate refresh outside the normal schedule.

## A symbol's price is never found

Check `symbols_missing_quotes` in the Positions entity's attributes, or Download Diagnostics. This means Yahoo Finance didn't recognize the symbol as you've written it in `holdings.yaml` — double-check the exact ticker (including any exchange suffix your holding needs, e.g. `.L` for London-listed, `-USD` for crypto pairs).
