# Dashboards

Portfolio Engine ships an official dashboard package: `dashboards/portfolio_engine_dashboard.yaml`, in this repository. It's a plain Lovelace YAML file — no custom cards, no HACS dependency — built entirely from Home Assistant's built-in `entities`, `glance`, and `markdown` cards, so it works on any Home Assistant install with nothing else added.

## Importing it

1. Open the file `dashboards/portfolio_engine_dashboard.yaml` in this repository and **find-and-replace every occurrence of `demo_portfolio`** with your own portfolio's folder name (the same ID from [Getting Started](GETTING_STARTED.md#your-first-portfolio) — whatever you named the subfolder under your investments path). Every entity ID in the file follows the pattern `sensor.<portfolio_id>_<metric>`, so this one substitution updates every reference at once.
2. In Home Assistant: Settings → Dashboards → Add Dashboard → "New dashboard from scratch". Give it a name (e.g. "Portfolio").
3. Open the new dashboard, click the three-dot menu (top right) → Edit Dashboard → three-dot menu again → **Raw configuration editor**.
4. Delete the placeholder content and paste in the file's content (with your substitution from step 1 applied).
5. Save.

If you track more than one portfolio, either duplicate the relevant sections for each portfolio ID, or create one dashboard per portfolio — both work equally well; which one to use is a personal preference about how you want to navigate between portfolios.

## What each view shows

- **Overview** — the headline numbers: current value, invested capital, profit, ROI, cash balance, both return metrics (MWR/TWR), and a quick status check (reconciliation, position count, transaction count).
- **Performance** — ROI, MWR, and TWR side by side, plus TWR's annualized figure (CAGR) and a plain-language explanation of what each number actually measures and how they differ.
- **Allocation** — every holding in a table (symbol, shares, value, gain %), plus concentration stats (largest position, top-5 concentration, diversification score).
- **Transactions** — your 10 most recent transactions in a table, plus the total transaction count.
- **Analytics** — dividend income (rolling 12-month, lifetime, yield), drawdown (current and maximum), and volatility.
- **Health** — reconciliation status with any specific discrepancies listed out, plus a check for missing price quotes or exchange rates.

## Customizing

Since this is plain Lovelace YAML with no custom cards, every part of it is editable the normal Home Assistant way — through the visual dashboard editor, or by continuing to hand-edit the raw YAML. Reasonable things to change:
- Reorder or remove views you don't care about.
- Add a `history-graph` card for `sensor.<portfolio>_value` if you want a value-over-time chart (this needs Recorder history for that entity, which is on by default).
- If you have [ApexCharts Card](https://github.com/RomRider/apexcharts-card) installed via HACS, it can produce richer allocation pie charts and performance graphs than the markdown-table approach this package uses — the official package deliberately doesn't require it, but nothing stops you from adding it yourself.

## Multiple currencies

The dashboard doesn't hardcode a currency symbol anywhere — it reads `unit_of_measurement` from your entities, which is your portfolio's own `base_currency`. No changes needed for a non-USD portfolio.
