# Portfolio Import & Assisted Setup

Two things this page covers: turning a reviewed broker-import report into real transactions, and creating a new portfolio without hand-writing YAML first.

## Applying a reviewed import

[Broker Import](BROKER_IMPORT.md) explains **Portfolio Engine: Import transactions** — it reads a broker export file and reports what's in it, but never writes to `transactions.yaml` itself. Once you've reviewed that report and you're happy with it, **Portfolio Engine: Apply import** writes its imported (non-duplicate) rows for you.

1. Run **Import transactions** as usual and review the report.
2. Run **Apply import**, giving it just the portfolio ID:

```yaml
service: portfolio_engine.apply_import
data:
  portfolio: demo_portfolio
```

```json
{
  "portfolio": "demo_portfolio",
  "applied_count": 2
}
```

This is all-or-nothing — every row the report marked `imported` gets written, nothing marked `duplicate` or `rejected` ever does. There's no way to apply only some of the imported rows in this version; if you want to exclude a specific one, hand-edit `transactions.yaml` afterward, the same way you'd correct any other entry.

Applying a report clears it — calling **Apply import** a second time without a fresh **Import transactions** first fails with a clear error rather than writing the same rows twice.

**What's the `.bak` file for?** Every write to `holdings.yaml`/`transactions.yaml` this integration makes keeps exactly one prior version alongside it (`transactions.yaml.bak`), overwritten on the next write — a quick "undo my last mistake," not a full history. For a complete backup, use **Portfolio Engine: Export portfolio data** first.

## Creating a new portfolio

### Your very first portfolio

If you're setting up Portfolio Engine for the first time and haven't created an investments folder yet, the Config Flow (Settings → Devices & Services → Add Integration → Portfolio Engine) will tell you the path doesn't exist. Tick **"Set up a new portfolio here"** on that same form instead of typing a different path, and it walks you through:

1. A name, base currency, and starting cash balance for your first portfolio.
2. Searching for holdings by name (the same lookup **Search assets** uses) and adding them one at a time — enter a query, pick the right match, fill in shares and average price, then search again or leave the query blank to finish.

This creates the folder and the portfolio in one step — no manual YAML required.

### Every portfolio after that

Once an investments path is configured, add further portfolios with **Portfolio Engine: Create portfolio**:

```yaml
service: portfolio_engine.create_portfolio
data:
  investments_path: investments
  portfolio_id: new_portfolio
  name: New Portfolio
  base_currency: USD
  cash_balance: 1000.0
  holdings:
    - symbol: AAPL
      shares: 10
      avg_price: 150.0
      currency: USD
      type: stock
```

```json
{
  "investments_path": "investments",
  "portfolio": "new_portfolio"
}
```

`holdings` is optional — omit it (or leave it empty) to create a portfolio with no holdings yet. Typically you'd build up each holding's `symbol`/`currency`/`type` from a prior **Search assets** call, then fill in `shares`/`avg_price` yourself.

This service never overwrites an existing portfolio — it fails if `portfolio_id` already has a `holdings.yaml`. It isn't available through Config Flow (that's only for the very first portfolio at initial setup); this is the way to add a second, third, or later portfolio under a path you've already configured.

## FAQ

**Can I edit a portfolio's holdings after creating it?**
Not through a service in this version — `create_portfolio` only creates. Hand-edit `holdings.yaml` the same way you would for a portfolio you'd set up manually.

**Does `create_portfolio` need the portfolio to already exist somewhere?**
No — `investments_path` just has to match an already-configured Portfolio Engine entry's path; `portfolio_id` is the *new* folder name it creates there.

**What if I call `apply_import` twice in a row?**
The second call fails with a clear error — there's nothing pending, since the first call already cleared the report. Run **Import transactions** again first if you want to apply another batch.

**Is the guided Config Flow setup the same thing as `create_portfolio`?**
They end up writing the exact same `holdings.yaml` shape, but Config Flow is only offered once, the first time a configured path doesn't exist yet — every portfolio after that uses the `create_portfolio` service instead.
