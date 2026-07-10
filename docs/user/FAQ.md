# FAQ

**Does Portfolio Engine connect to my broker?**
No. It reads plain YAML files you maintain yourself. There's no broker integration, no account linking, and no automated trading of any kind.

**Can it place trades or modify my portfolio?**
No. It's entirely read-only with respect to your investments — it computes and displays, never writes back to your holdings or executes anything.

**Where does price data come from?**
Yahoo Finance's public quote endpoints, which need no API key or account.

**What's the difference between ROI, MWR, and TWR?**
- **ROI** is the simplest: total profit divided by total invested. It doesn't account for *when* money went in or out.
- **MWR (Money-Weighted Return / XIRR)** is annualized and sensitive to the timing and size of your deposits/withdrawals — it reflects your personal outcome, including the effect of your own timing decisions.
- **TWR (Time-Weighted Return)** removes the effect of deposit/withdrawal timing entirely — it reflects the portfolio's own investment performance, the number a fund manager would be judged on, independent of when you happened to add or remove money.

Two people holding the exact same investments can have different MWR (if they deposited at different times) but identical TWR.

**Why is Time-Weighted Return "unknown" right after I set things up?**
TWR needs at least one prior day's snapshot to measure a return between two points in time. Portfolio Engine takes one snapshot per calendar day automatically — the metric becomes available starting the day after your first snapshot exists.

**Can I track multiple portfolios?**
Yes — one subfolder per portfolio under your investments path, each gets its own complete set of entities.

**Can I track multiple currencies in one portfolio?**
Yes. Each holding declares its own currency; the portfolio's `base_currency` is what totals are reported in, converted automatically using current exchange rates.

**What happens if I make a mistake in a transaction?**
Don't edit or delete the original entry — the transaction log is meant to be append-only, a permanent record. Add a new transaction correcting it instead (e.g. a `sell` reversing an incorrect `buy`).

**Does deleting the integration delete my data?**
Your `holdings.yaml`/`transactions.yaml` files are untouched — they're just files in your investments folder, unaffected by the integration's own lifecycle. Snapshot history (stored via Home Assistant's own storage, not your investments folder) is deleted along with the config entry when you remove it.

**Is my data sent anywhere?**
Only symbol lookups (to fetch quotes) and currency pairs (to fetch exchange rates) go out, to Yahoo Finance's public endpoints — no holdings amounts, transaction history, or portfolio values are ever transmitted anywhere. Diagnostics downloads stay local to your Home Assistant instance unless you choose to share the file yourself.

**Why does the dashboard package need me to find-and-replace an entity prefix?**
Every entity ID includes your portfolio's own folder name (e.g. `sensor.my_portfolio_value`), which is different for everyone — there's no way to ship a dashboard with the "right" prefix pre-filled for every possible user. See [Dashboards](DASHBOARDS.md) for the exact steps.

**Something's not covered here — where do I ask?**
Check [Troubleshooting](TROUBLESHOOTING.md) first, then open an issue in this repository with your Download Diagnostics output attached (see Troubleshooting's last section) — it gives maintainers everything needed to help without you having to describe your whole setup by hand.
