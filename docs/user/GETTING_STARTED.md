# Getting Started

## Your first portfolio

Inside the investments folder path you gave during setup, create one subfolder per portfolio you want tracked. The folder's name becomes that portfolio's ID, which shows up in every entity ID it creates — a folder named `retirement` gives you entities like `sensor.retirement_value`, `sensor.retirement_roi`, and so on.

Inside that subfolder, create `holdings.yaml`:

```yaml
base_currency: USD
cash_balance: 1500.00
holdings:
  - symbol: AAPL
    shares: 10
    avg_price: 145.32
    currency: USD
    type: stock
  - symbol: VOO
    shares: 5
    avg_price: 410.00
    currency: USD
    type: etf
  - symbol: BTC-USD
    shares: 0.25
    avg_price: 42000.00
    currency: USD
    type: crypto
```

- **`base_currency`** — the currency your portfolio's totals are reported in. Individual holdings can be in a different currency (Portfolio Engine converts automatically using current exchange rates).
- **`cash_balance`** — uninvested cash sitting in the account, in `base_currency`.
- **`symbol`** — the ticker symbol as Yahoo Finance recognizes it. Most US stocks and ETFs are just the ticker (`AAPL`, `VOO`); crypto usually needs a `-USD` suffix (`BTC-USD`); some non-US exchanges need a suffix too (e.g. `.L` for London). If a symbol isn't recognized, that holding's quote will be missing — check Settings → Devices & Services → Portfolio Engine → Download Diagnostics, or the `symbols_missing_quotes` attribute on the Positions entity, to see which ones.
- **`avg_price`** — your average cost basis per share/unit, in the holding's own currency (not `base_currency`).
- **`type`** — a free-text label (`stock`, `etf`, `crypto`, `fund`, or anything else you want) used for the allocation breakdown.

Once this file exists, reload the integration (Settings → Devices & Services → Portfolio Engine → ⋮ → Reload) or wait for the next update interval, and you'll see a new device with the core entities: Value, Total Invested, Total Profit, ROI, Cash Balance, and Positions.

## Adding transaction history

Everything in the previous section gets you current value and simple ROI. To unlock reconciliation, money-weighted return, dividend income, and transaction-count tracking, add `transactions.yaml` in the same portfolio folder:

```yaml
transactions:
  - id: "buy-aapl-1"
    type: buy
    date: "2024-03-15T00:00:00Z"
    symbol: AAPL
    shares: 10
    price: 145.32
    amount: 1453.20
    currency: USD
  - id: "deposit-1"
    type: deposit
    date: "2024-01-01T00:00:00Z"
    amount: 5000.00
    currency: USD
  - id: "dividend-1"
    type: dividend
    date: "2024-06-15T00:00:00Z"
    symbol: AAPL
    amount: 12.50
    currency: USD
```

- **`id`** — any string, unique within this file. If you omit it, one is generated for you automatically.
- **`type`** — one of `buy`, `sell`, `dividend`, `deposit`, `withdrawal`, `fee`, `transfer_in`, `transfer_out`.
- **`amount`** — always a positive number (`buy`/`sell`/`deposit`/`withdrawal` all use unsigned amounts — the `type` alone determines whether it added or removed cash, so you never have to remember a sign convention).
- **`transfer_in`/`transfer_out`** are for shares that arrive or leave without a cash transaction (e.g. moving shares between brokers) — `amount` should be `0` for these; `shares`/`price` still describe what moved.

Transactions are **append-only** — the log is meant to be a permanent record. If you made a mistake, add a new transaction correcting it (e.g. a `sell` reversing an incorrect `buy`) rather than editing or deleting the original entry; note the correction in a `notes` field if you want the reason on record.

### The Reconciliation entity

Once you have both `holdings.yaml` and `transactions.yaml`, the Reconciliation entity checks that they agree with each other — replaying your transaction log should arrive at the same shares/cash balance you declared in `holdings.yaml`. If they don't match (a common cause: you updated `holdings.yaml` after a real-world trade but forgot to also log the transaction, or vice versa), you'll see `discrepancy` instead of `ok`, and — as of this version — an actual Home Assistant Repair issue prompting you to fix it (see [Troubleshooting](TROUBLESHOOTING.md)).

## Snapshots (automatic — nothing to configure)

Once your portfolio is set up, Portfolio Engine automatically records one snapshot of your portfolio's value per calendar day — no configuration needed, and no separate file to maintain. This history is what powers time-weighted return, drawdown, and volatility. There's nothing to "enable" here; it starts happening from your very first successful refresh. The only thing to know is that these metrics need a few days of history to become meaningful — on day one, you'll see `unknown` for Time-Weighted Return, Drawdown, and Volatility, and that's expected, not a problem (check each entity's `status` attribute, which will say `no_data` or `insufficient_data`).

## What's next

- [Import the dashboard](DASHBOARDS.md) to see all of this laid out visually instead of hunting through entity lists.
- If something looks wrong, [Troubleshooting](TROUBLESHOOTING.md) covers the most common issues.
