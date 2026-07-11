# Finding the Right Ticker

Adding a holding to `holdings.yaml` requires knowing its exact Yahoo Finance ticker — `VWCE.DE`, not "Vanguard FTSE All-World"; `IWDA.AS`, not "iShares Core MSCI World." If you already know your ticker, you don't need this. If you don't, **Portfolio Engine: Search assets** looks it up for you by name.

**It never reads or writes any portfolio file.** This is a pure lookup against Yahoo Finance — it has no idea what portfolios you have configured, and it can't change anything even if it wanted to. You still add the result to `holdings.yaml` yourself, the same way [Getting Started](GETTING_STARTED.md) describes.

## Running a search

1. Go to Developer Tools → Actions.
2. Choose the action **Portfolio Engine: Search assets**.
3. Fill in:
   - **Query** — a company or fund name, or a partial ticker (e.g. `Vanguard FTSE All-World`, `Apple`, `AAPL`).
   - **Limit** — optional, how many matches to return (1–25, defaults to 10).
4. Run it with **Response variable** enabled (or `return_response: true` in YAML) to see the results.

## Example

```yaml
service: portfolio_engine.search_assets
data:
  query: "Vanguard FTSE All-World"
  limit: 5
```

```json
{
  "query": "Vanguard FTSE All-World",
  "count": 1,
  "results": [
    {
      "symbol": "VWCE.DE",
      "name": "Vanguard FTSE All-World UCITS ETF",
      "exchange": "XETRA",
      "currency": "EUR",
      "asset_type": "etf"
    }
  ]
}
```

## Reading the results

Each result maps directly onto a `holdings.yaml` entry:

| Result field | `holdings.yaml` field |
|---|---|
| `symbol` | `symbol` |
| `currency` | `currency` |
| `asset_type` | `type` |
| `exchange` | (informational only — not a `holdings.yaml` field; tells you *which* market this ticker trades on) |
| `name` | (informational only — for your own reference) |

`asset_type` is always one of `stock`, `etf`, `mutual_fund`, or `crypto` — the same vocabulary `holdings.yaml`'s `type` field already uses, so you can copy it across without translation.

## Why more than one match?

The same company or fund often trades on multiple exchanges, in different currencies — Apple trades on NASDAQ in USD, but also on several European exchanges in EUR. Each is a genuinely different ticker with a genuinely different `symbol`/`exchange`/`currency` combination, and only one of them is the one your broker actually gave you shares in. Pick the result matching your broker's own confirmation or statement, not just the first one back.

## FAQ

**Will this write anything to my configuration?**
No. Never. It's a read-only lookup against Yahoo Finance — nothing about your portfolios, holdings, or transactions is read or touched.

**Why didn't it find what I was searching for?**
Only stocks, ETFs, mutual funds, and crypto are returned — indices, futures, options, and currency pairs are filtered out, since `holdings.yaml` has no matching `type` for them. Try a more specific name, or the ticker itself if you know part of it.

**Can I search across multiple portfolios at once, or scope a search to one portfolio?**
There's no portfolio scoping at all — this is a general Yahoo Finance lookup, independent of anything you've configured. Run it before you've set up any portfolio, or with several configured; it behaves identically either way.

**Does this need a portfolio configured to work?**
No — the Home Assistant integration needs at least one portfolio configured for the service to be registered at all (same as every other Portfolio Engine service), but the search itself has nothing to do with which portfolio, or how many.
