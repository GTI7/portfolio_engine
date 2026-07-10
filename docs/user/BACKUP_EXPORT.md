# Backing Up a Portfolio

Portfolio Engine can write a complete backup of one portfolio to a single JSON file: every holding, the full transaction history, the entire snapshot history, and the last broker import report (if any). This is a genuine copy of your data, independent of Home Assistant — useful before a risky edit, before an OS/HA reinstall, or just as a periodic safety net.

## Running an export

1. Go to Developer Tools → Actions.
2. Choose the action **Portfolio Engine: Export portfolio data**.
3. Fill in:
   - **Portfolio** — the portfolio ID (the folder name under your investments path).
   - **Output file path** — where to write the backup, relative to your Home Assistant config directory (e.g. `backups/demo_portfolio_2026-07-10.json`). Parent folders are created automatically if they don't already exist.
4. Run it. The action returns a short summary (holdings/transactions/snapshots counts, the exact path written).

## What's in the file

```json
{
  "exported_at": "2026-07-10T12:00:00+00:00",
  "portfolio_id": "demo_portfolio",
  "portfolio_name": "Demo Portfolio",
  "base_currency": "USD",
  "cash_balance": 1000.0,
  "holdings": [ { "symbol": "AAPL", "shares": 10, "avg_price": 150.0, "currency": "USD", "type": "stock", "account": null } ],
  "transactions": [ { "id": "...", "type": "buy", "date": "...", "amount": 1500.0 } ],
  "snapshots": [ { "id": "...", "timestamp": "...", "portfolio_value": 2500.0 } ],
  "last_import": null
}
```

`holdings` and `transactions` are read directly from your `holdings.yaml`/`transactions.yaml` files at export time — not from whatever the last coordinator refresh happened to compute, so the backup reflects your actual source files exactly. `snapshots` is your full history from Home Assistant's own storage (not just the "recent" summaries the dashboard shows). `last_import` is the most recent broker import report for this portfolio, if you've run one (`null` otherwise).

## What this is *not*

This is a **read-only snapshot**, not a sync mechanism and not a restore tool. Portfolio Engine has no "import a backup" service — restoring from one means manually copying the `holdings`/`transactions` sections back into your `holdings.yaml`/`transactions.yaml` files yourself, the same deliberate "you review, you write" principle [broker import](BROKER_IMPORT.md) follows. This keeps the same guarantee: nothing in this integration ever silently rewrites your source-of-truth files.

## A reasonable habit

There's no built-in scheduling for this — Portfolio Engine doesn't run exports automatically. If you want a periodic backup, a simple Home Assistant automation calling this action on a schedule (e.g. weekly) works well:

```yaml
automation:
  - alias: "Weekly portfolio backup"
    trigger:
      - platform: time
        at: "03:00:00"
    condition:
      - condition: time
        weekday: [sun]
    action:
      - action: portfolio_engine.export_portfolio_data
        data:
          portfolio: demo_portfolio
          output_path: "backups/demo_portfolio_{{ now().strftime('%Y-%m-%d') }}.json"
```

(Building the automation itself is outside Portfolio Engine's scope — this is just a plain Home Assistant automation calling the service, no different from any other action-triggering automation.)
