# Importing Transactions from a Broker

Portfolio Engine can read a broker's export file and tell you what's in it — how many transactions, which ones look new, which ones look like duplicates of what you already have, and which ones it couldn't understand. **It never edits `transactions.yaml` for you.** You review the report, then add the transactions yourself, the same way you would if you'd typed them in by hand.

This is deliberate, not a missing feature: your transaction log is the one thing in this integration you're expected to fully trust, and an automatic write is exactly the kind of thing that's hard to safely undo if a broker's export format changes unexpectedly or a duplicate check has a false negative. A report you review costs you a few minutes; a silent wrong write costs you a corrupted financial record.

## Supported formats

- **Generic CSV** — a documented, simple column schema (see below). Use this if your broker doesn't have a dedicated importer, or if you're comfortable reshaping an export into this format yourself.
- **Interactive Brokers Flex Query (XML)** — targets IBKR's standard Trade and CashTransaction field names. Flex Query templates are user-configurable, so a heavily customized template may need adjustment — see the IBKR-specific notes below.

More formats can be added later without touching anything else — each one is a self-contained "read this format, produce Transaction objects" translator, and the rest of the integration (validation, reconciliation, MWR, TWR, every other calculator) has no idea any of this exists.

## Running an import

1. Get your broker's export file onto your Home Assistant instance, somewhere under your config directory (e.g. create an `imports/` folder and place it there, the same way you'd add any file).
2. Go to Developer Tools → Actions (or Settings → Automations & Scenes → Scripts, if you want to build this into something reusable).
3. Choose the action **Portfolio Engine: Import transactions**.
4. Fill in:
   - **Portfolio** — the portfolio ID (the folder name under your investments path).
   - **Provider** — `Generic CSV` or `Interactive Brokers Flex Query (XML)`.
   - **File path** — the export file's path, relative to your Home Assistant config directory (e.g. `imports/broker_export.csv`).
5. Run it. The action returns a report: how many rows were read, how many are new, how many look like duplicates, how many couldn't be parsed, and any warnings.

The same summary also updates `sensor.<portfolio>_last_import` (state = imported count; attributes = provider, timestamp, full counts, warnings) and the dashboard's Import view, so you don't have to re-run the action just to see the last result again.

## Reviewing the report

- **Imported** — transactions that look genuinely new. These are what you should consider adding to `transactions.yaml`.
- **Duplicates** — transactions that match something already in your log, either by exact ID or by a date+symbol+shares+amount match. These are deliberately *not* silently dropped — the report tells you they were found, so you can confirm the match is correct rather than trusting an automatic decision.
- **Rejected** — rows that failed the same validation every hand-typed transaction goes through (e.g. a `buy` row missing a share count). The report includes the specific error for each one, so you know exactly what to fix in the source file if you want to re-export and try again.
- **Warnings** — anything noteworthy that isn't an error (e.g. a cash transaction type the importer doesn't have a category for, like broker-paid interest — skipped, not guessed at).

## Adding the imported transactions to your log

Copy the imported transactions' details into `transactions.yaml` yourself, in the same format as [Getting Started](GETTING_STARTED.md#adding-transaction-history) describes. If a transaction came with a broker-native reference (e.g. IBKR's `transactionID`), the importer already gave it a stable ID (prefixed `ibkr-`) — keep that ID when you copy it in, so a future re-import of the same period correctly recognizes it as a duplicate instead of importing it again.

Prefer not to copy things by hand? **Portfolio Engine: Apply import** will write the report's imported rows to `transactions.yaml` for you, once you've reviewed them — see [Portfolio Import & Setup](PORTFOLIO_IMPORT_AND_SETUP.md).

## Generic CSV column schema

```csv
id,type,date,symbol,shares,price,amount,currency,notes
t1,buy,2026-01-15T00:00:00Z,AAPL,10,150.25,1502.50,USD,
d1,deposit,2026-01-01T00:00:00Z,,,,1000.00,USD,initial funding
```

- **Required:** `type`, `date`, `amount`, `currency`.
- **Optional:** `id` (auto-generated if blank — see note below), `symbol`/`shares`/`price` (required for `buy`/`sell`, must be blank for everything else), `notes`.
- **`date`** must be ISO 8601 (`2026-01-15T00:00:00Z` or `2026-01-15T00:00:00+00:00`).
- **`type`** is one of `buy`, `sell`, `dividend`, `deposit`, `withdrawal`, `fee`, `transfer_in`, `transfer_out` — same vocabulary as `transactions.yaml`.

If a row has no `id`, the importer generates one deterministically from the row's own content (not a random ID) — re-importing the exact same file twice produces the same generated ID both times, so the duplicate check can actually recognize a repeat import even without your file providing its own IDs.

## Interactive Brokers Flex Query notes

Set up an **Activity Flex Query** in IBKR's Account Management (Performance & Reports → Flex Queries) that includes the **Trades** and **Cash Transactions** sections, exported as **XML**. This importer looks for the standard field names IBKR uses by default (`symbol`, `tradeDate`, `quantity`, `tradePrice`, `buySell`, `currency`, `transactionID` for trades; `type`, `amount`, `dateTime`, `currency`, `transactionID` for cash transactions) — if your template is heavily customized and renames or omits these, the importer may not recognize some rows (they'll show up as rejected with a specific error, not silently skipped).

Recognized cash transaction types: **Dividends**, **Deposits/Withdrawals** (split into deposit or withdrawal by the amount's sign), **Fees**/**Other Fees**. Anything else (broker-paid interest, withholding tax, etc.) is reported as a warning and skipped — these fall outside Portfolio Engine's transaction categories, not because they're unimportant, but because there's no matching `TransactionType` to translate them into yet.

## FAQ

**Will this overwrite my existing transactions.yaml?**
No. Never. The service only produces a report.

**What if I run the same import twice by accident?**
The duplicate check should catch it — every transaction from the second run will show up in the report's `duplicates` count instead of `imported`, as long as you've already added the first run's results to your actual log (the duplicate check compares against your current `transactions.yaml`, not against the import history itself).

**Can I import into a portfolio that doesn't exist yet?**
No — create the portfolio first (by hand, per [Getting Started](GETTING_STARTED.md), or with **Portfolio Engine: Create portfolio** / the Config Flow's guided setup — see [Portfolio Import & Setup](PORTFOLIO_IMPORT_AND_SETUP.md)). The import service looks up an already-configured portfolio by ID.
