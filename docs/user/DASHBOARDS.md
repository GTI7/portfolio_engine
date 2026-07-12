# Dashboards

Portfolio Engine ships an official dashboard package: `dashboards/portfolio_engine_dashboard.yaml`, in this repository. It's plain Lovelace YAML — no custom cards, no HACS dependency, no Dashboard Strategy, no frontend JavaScript — built from Home Assistant's own native card types (`entities`, `gauge`, `history-graph`, `statistics-graph`), with `markdown` used only where no native card can do the job: the holdings/transactions tables, a couple of nested-attribute summaries, and a few pieces of conditional or static explanatory text.

## Why one small edit is still needed

Native cards like `entities` and `gauge` bind to a fixed entity ID at config time — Home Assistant has no way to template *which* entity a native card shows. So this package can't be 100% edit-free the way a markdown-only dashboard could be; that tradeoff was deliberate (see `MILESTONE_13_DESIGN.md`'s "Option A vs Option B" section) — native cards give you real click-to-more-info, native theming, a real gauge, and real history/statistics charts, none of which a markdown-simulated equivalent can fully replicate. The one-time cost is small: every entity ID in this file is defined **exactly once**, as a YAML anchor, in the Overview view — every other card in the file just references that same definition.

## Importing it

1. Open `dashboards/portfolio_engine_dashboard.yaml` and find the **Overview** view — its four `entities` cards are the configuration block. Every line looks like:
   ```yaml
   - entity: &value sensor.demo_portfolio_value
   ```
   The `&value` part is a YAML anchor — it names this value so it can be reused elsewhere in the file via `*value`. Replace `demo_portfolio` with your own portfolio's folder name (the same ID from [Getting Started](GETTING_STARTED.md#your-first-portfolio)) in these lines. The simplest way: find-and-replace `demo_portfolio` across the whole file in one pass — this correctly updates the Overview anchors *and* the handful of markdown cards elsewhere that also need your portfolio ID (see "The six remaining literal references" below).
2. In Home Assistant: Settings → Dashboards → Add Dashboard → "New dashboard from scratch". Give it a name (e.g. "Portfolio").
3. Open the new dashboard, click the three-dot menu (top right) → Edit Dashboard → three-dot menu again → **Raw configuration editor**.
4. Delete the placeholder content and paste in the file's content, with your substitution from step 1 applied.
5. Save.

### Worked example

Before editing, the Overview view's "At a Glance" card reads:

```yaml
- type: entities
  title: At a Glance
  entities:
    - entity: &value sensor.demo_portfolio_value
    - entity: &invested sensor.demo_portfolio_total_invested
```

If your portfolio's folder is `my_portfolio`, after a single find-and-replace of `demo_portfolio` → `my_portfolio` across the whole file, it reads:

```yaml
- type: entities
  title: At a Glance
  entities:
    - entity: &value sensor.my_portfolio_value
    - entity: &invested sensor.my_portfolio_total_invested
```

Nothing else needs to change — every `gauge`, `history-graph`, `statistics-graph`, and other `entities` card elsewhere in the file references `*value`/`*invested`/etc., not a literal entity ID, so it updates automatically.

### The six remaining literal references

YAML anchors substitute a whole value, not a fragment inside a larger string — so the six `markdown` cards that need Jinja (the Holdings table, the Holdings view's best/worst-performer card, the Transactions table, and Administration's three status/detail cards) each have their own single line near the top of their template:
```yaml
{% set portfolio_id = 'demo_portfolio' %}
```
A whole-file find-and-replace of `demo_portfolio` (as described above) updates these six lines at the same time as the Overview anchors — you don't need to hunt for them separately, but they're clearly commented if you ever want to edit precisely rather than blanket-replace.

**If you already imported an older copy of this file** (a fully markdown-based version that auto-discovered portfolios with no editing at all, or an even older version requiring find-and-replace everywhere), it keeps working exactly as it did — nothing about your entities changed. Re-importing this version is optional.

### Multiple portfolios

Anchor names must be unique within one file, so tracking a second portfolio means duplicating the relevant view(s) and giving the copies new anchor names (e.g. `&value2` instead of `&value`) — this is the same one-time edit as the first portfolio, repeated per portfolio, not an automatic add. If you'd rather not maintain multiple anchor sets in one file, creating one dashboard per portfolio (each with its own single-portfolio anchor block) works equally well.

## What each view shows

- **Overview** — "How am I doing, right now?" The headline numbers (native `entities` cards: value, today's change, invested capital, profit, ROI, cash balance, both return metrics, a quick status check) plus a native `history-graph` chart of value over time, and an "Additional Metrics" card holding the entity IDs used by later views.
- **Holdings** — "What do I actually own, and how concentrated am I?" Every holding in a table (symbol, shares, value, gain % — markdown, since no native card renders a table from a list-valued attribute; a holding whose latest quote fetch failed shows "Price unavailable" rather than a fabricated value), two native rows showing your largest allocation group's name and its share of the portfolio (the full breakdown lives in that entity's own attributes), a native `gauge` for largest-position concentration, native attribute rows for top-5 concentration and diversification score, and a small markdown card for the best/worst performer (their names live inside a nested attribute, which no native row type can format; any of the three currently affected by a missing quote is flagged as unavailable rather than shown with a fabricated result).
- **Performance** — "How well is my money working, and by which measure?" A native ROI `gauge`, a native `entities` card with ROI/MWR/TWR plus TWR's annualized figure (CAGR), a native `statistics-graph` of ROI over time, and a static markdown card explaining what the three numbers mean and how they differ.
- **Transactions** — "What has actually happened recently?" A native `entities` card for the total count, plus a markdown table of your 10 most recent transactions, with a "Transaction Notes" section that only appears when one of those transactions carries a note (e.g. a backfilled-deposit reminder).
- **Analytics** — "What income am I generating, and how much risk am I carrying?" Fully native — dividend income, drawdown, and volatility, each with their own detail attributes shown as native rows (lifetime, this year, yield, average monthly; maximum drawdown, peak value, recovery status; daily volatility, observation period, sample count).
- **Administration** — "Can I trust this data, and what do I do if I can't?" A native reconciliation status row, markdown for the specific discrepancy list and data-availability warnings (genuinely conditional text), a native last-import status row, markdown for the import details and a backup/diagnostics pointer.

## Customizing

Since every card here is either a native Lovelace card or plain markdown, every part of it is editable the normal Home Assistant way — through the visual dashboard editor, or by continuing to hand-edit the raw YAML. Reasonable things to change:
- Reorder or remove views you don't care about.
- Add more `history-graph`/`statistics-graph` cards for other entities (e.g. dividend income over time) — alias the entity the same way the shipped cards do.
- If you have [ApexCharts Card](https://github.com/RomRider/apexcharts-card) installed via HACS, it can produce richer allocation pie charts than this package's native gauge/attribute rows — the official package deliberately doesn't require it, but nothing stops you from adding it yourself.

## Multiple currencies

The dashboard doesn't hardcode a currency symbol anywhere for the entity-bound cards — Home Assistant renders each entity's own `unit_of_measurement`, which is your portfolio's own `base_currency`. The four "portfolio currency"-suffixed attribute rows in Analytics (dividend lifetime/this-year/average-monthly, drawdown peak value) show a generic `(portfolio currency)` label instead of the specific symbol, since a native attribute row's suffix is a fixed string, not a template — check the corresponding entity's own unit if you want the exact symbol.
