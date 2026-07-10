# Home Assistant Investment Dashboard — Architecture & Implementation Guide

**Target instance:** Home Assistant Core 2026.7.1, HACS-managed, 11 areas, 373 entities.

## 0. What I found on your instance first

Before designing anything, I checked your live system so this plan fits what you actually have rather than a generic template:

| Item | Status | Implication |
|---|---|---|
| **Yahoo Finance integration** (`iprak/yahoofinance`, HACS) | Installed via HACS, **not yet configured**, and there's a pending "restart required" repair for it | This becomes your primary price-feed source. Restart HA, then add symbols through the config entry (Settings → Devices & Services → Add Integration → Yahoo Finance). |
| **ApexCharts Card** (`RomRider/apexcharts-card`) | Installed, v2.2.3 | Use this for every time-series chart (price history, portfolio value over time, dividend history). It's already the right choice per your spec. |
| **Mushroom Cards** | Not installed | Needed for the overview/KPI tiles. Install via HACS → Frontend. |
| **auto-entities** | Not installed | Needed for the Portfolio table and Watchlist (dynamic entity lists). Install via HACS → Frontend. |
| **flex-table-card** | Not installed | Recommended addition — better fit than auto-entities for true tabular holdings data with sorting. Install via HACS → Frontend. |
| **Plotly / Bubble Card** | Not installed | Optional; I'll note where they'd help but the core design doesn't require them. |
| **No existing finance packages/sensors** | — | You're building this from scratch — good, no legacy conflicts to work around. |

**Action item before anything else:** restart Home Assistant to clear the Yahoo Finance repair, then install `mushroom`, `auto-entities`, and `flex-table-card` from HACS → Frontend. Everything below assumes those four cards/integration are available.

---

## 1. System Architecture

### 1.1 The core scalability problem

Your spec's hardest requirement is: *"adding a new asset should only require updating a single configuration source."* Home Assistant's naive approach — one `template sensor` per metric per holding — breaks this immediately: a 20-asset portfolio needs `20 assets × 6 sensors = 120` hand-written sensors, and every new metric multiplies that.

The design below avoids that by splitting the problem into two layers:

1. **A single data source** — one YAML file listing your holdings (symbol, shares, cost basis, type, currency). Adding an asset = adding one 5-line block here.
2. **A small number of aggregate template sensors** that *iterate* over that data source with Jinja loops, rather than one sensor per asset. Per-asset detail is exposed as **attributes** on one or two sensors, not as dozens of separate entities.

This mirrors how the built-in Energy Dashboard works internally (one config store, computed views), which is the benchmark your spec asks for.

### 1.2 High-level diagram

```
┌─────────────────────────────────────────────────────────────┐
│  DATA LAYER                                                  │
│  packages/investment/holdings.yaml   ← single source of truth│
│  (list of assets: symbol, shares, cost basis, type, currency)│
└───────────────┬───────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────┐
│  PRICE FEED LAYER                                             │
│  Yahoo Finance integration → sensor.yahoofinance_<SYMBOL>     │
│  (one native sensor per symbol, auto-created by the           │
│   integration when you add it — no YAML needed here)          │
└───────────────┬───────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────┐
│  COMPUTE LAYER  (packages/investment/sensors_*.yaml)          │
│  • sensor.portfolio_holdings   → list-valued attribute,       │
│    one dict per asset, computed via Jinja for-loop            │
│  • sensor.portfolio_summary    → total value, gain/loss,      │
│    ROI, allocation %                                          │
│  • sensor.portfolio_history_*  → daily/weekly/monthly deltas  │
│    via utility_meter / statistics                             │
│  • sensor.asset_<SYMBOL>_detail → optional, only for assets   │
│    that need a dedicated detail page                          │
└───────────────┬───────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────┐
│  PRESENTATION LAYER  (dashboards/*.yaml, Lovelace)             │
│  Overview · Portfolio · Allocation · Asset Detail · Market ·   │
│  Watchlist · Dividends · Performance · Goals · Analytics       │
│  Mushroom (KPIs) · flex-table-card (tables) ·                  │
│  ApexCharts (history) · auto-entities (dynamic lists)          │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Why this beats "one sensor per asset per metric"

- **Adding an asset** = one block in `holdings.yaml` + adding the symbol to the Yahoo Finance integration options. No new template sensors, no new dashboard cards.
- **Adding a metric** (e.g. dividend yield) = one line added to the Jinja loop in `sensor.portfolio_holdings`, applied to every asset at once.
- **Dashboards read attributes, not entities.** `flex-table-card` and `auto-entities` can both render a table straight from a single sensor's list-valued attribute, so the Portfolio, Allocation, and Watchlist dashboards need zero per-asset card duplication.

---

## 2. Recommended Folder Structure

```
config/
├── configuration.yaml
├── packages/
│   └── investment/
│       ├── holdings.yaml              # the single source of truth (assets, cash, goals)
│       ├── sensors_portfolio.yaml     # aggregate + per-asset template sensors
│       ├── sensors_performance.yaml   # utility_meter / statistics-based history sensors
│       ├── sensors_dividends.yaml     # dividend tracking sensors
│       ├── helpers.yaml               # input_number/input_text/input_boolean helpers
│       ├── automations.yaml           # all investment-related automations
│       └── scripts.yaml               # notification/report-generation scripts
├── dashboards/
│   └── investment/
│       ├── 00_overview.yaml
│       ├── 01_portfolio.yaml
│       ├── 02_allocation.yaml
│       ├── 03_asset_detail.yaml
│       ├── 04_market.yaml
│       ├── 05_watchlist.yaml
│       ├── 06_dividends.yaml
│       ├── 07_performance.yaml
│       ├── 08_goals.yaml
│       └── 09_analytics.yaml
└── www/
    └── investment/
        └── logos/                     # optional local asset icons
```

`configuration.yaml` only needs:

```yaml
homeassistant:
  packages: !include_dir_named packages/investment

lovelace:
  mode: yaml
  dashboards:
    investment-dashboard:
      mode: yaml
      title: Investments
      icon: mdi:finance
      show_in_sidebar: true
      filename: dashboards/investment/00_overview.yaml
```

Using **packages** (rather than scattering sensors across the global `sensor:` block) is what keeps this maintainable — everything investment-related lives under `packages/investment/`, can be reloaded independently (Developer Tools → YAML → "Template Entities" reload, no full restart), and is trivially removable if you ever want to disable the whole feature.

---

## 3. Entity Naming Conventions

Consistency here is what makes the Jinja loops in Section 5 possible without special-casing.

| Entity | Pattern | Example |
|---|---|---|
| Yahoo Finance price sensor (native) | `sensor.yahoofinance_<SYMBOL>` | `sensor.yahoofinance_aapl` |
| Portfolio holdings (list attribute) | `sensor.portfolio_holdings` | — |
| Portfolio summary (KPIs) | `sensor.portfolio_summary` | — |
| Per-asset detail sensor (only where needed) | `sensor.asset_<symbol>_detail` | `sensor.asset_aapl_detail` |
| Allocation sensors | `sensor.allocation_<dimension>` | `sensor.allocation_asset_class`, `sensor.allocation_currency` |
| Market index sensors | `sensor.market_<index>` | `sensor.market_sp500`, `sensor.market_vix` |
| Watchlist entries | part of `sensor.watchlist_items` attribute list | — |
| Dividend sensors | `sensor.dividend_<scope>` | `sensor.dividend_monthly_expected`, `sensor.dividend_income_ytd` |
| Goal helpers | `input_number.goal_<name>` | `input_number.goal_portfolio_target` |
| Cash helper | `input_number.cash_available_<currency>` | `input_number.cash_available_eur` |
| Automations | `Investment: <Action>` | `Investment: Daily Portfolio Summary` |
| Scripts | `script.investment_<purpose>` | `script.investment_generate_daily_summary` |

Rules:
- Symbols are always **lowercase** in entity IDs, **uppercase** in display attributes (`AAPL`).
- Every currency-valued attribute is suffixed with its ISO code in a companion attribute (`value_eur`, not baked into the name) so multi-currency portfolios don't require separate entities per currency.
- Never encode a metric into the entity_id when it could be an attribute (`sensor.portfolio_summary` has attributes `daily_change_pct`, `weekly_change_pct`, etc. — not five separate sensors).

---

## 4. Data Source: `holdings.yaml`

This is the file you edit whenever your portfolio changes. Everything downstream derives from it.

```yaml
# packages/investment/holdings.yaml
input_text:
  portfolio_holdings_raw:
    name: Portfolio Holdings (raw JSON)
    initial: >
      [
        {"symbol": "AAPL",  "name": "Apple Inc.",        "type": "stock", "currency": "USD", "shares": 12,  "avg_price": 165.20},
        {"symbol": "VWCE.DE","name": "Vanguard FTSE All-World", "type": "etf", "currency": "EUR", "shares": 40, "avg_price": 105.10},
        {"symbol": "MSFT",  "name": "Microsoft Corp.",    "type": "stock", "currency": "USD", "shares": 8,   "avg_price": 310.00},
        {"symbol": "BTC-USD","name": "Bitcoin",           "type": "crypto","currency": "USD", "shares": 0.15,"avg_price": 42000.00}
      ]
    max: 8000

input_number:
  cash_available_eur:
    name: Cash Available (EUR)
    min: 0
    max: 1000000
    step: 0.01
    unit_of_measurement: "€"
    mode: box

  goal_portfolio_target:
    name: Portfolio Target Value
    min: 0
    max: 10000000
    step: 1000
    unit_of_measurement: "€"
    mode: box

  goal_monthly_contribution:
    name: Planned Monthly Contribution
    min: 0
    max: 100000
    step: 10
    unit_of_measurement: "€"
    mode: box
```

**Why `input_text` holding JSON, not `input_number` per field?** It's the one helper type that can hold a structured list without exploding into per-asset entities. You edit it via the UI (Settings → Devices & Services → Helpers) or directly in YAML. If your portfolio changes rarely, this is the simplest possible "single configuration source." If you want a friendlier editing UI later, the same list can be swapped for a small local **file sensor** (`file:` platform reading a `holdings.json` you edit in the File Editor add-on) or a tiny **pyscript** service — same downstream architecture either way.

> **Scalability note:** `input_text` has an 8000-character limit (settable up to 255 by default, raised with `max:` as shown). That comfortably covers 40–60 holdings. If you expect to exceed that, switch the source to a `file` sensor reading raw JSON from `/config/packages/investment/holdings.json` — the rest of the architecture doesn't change, only where `sensor.portfolio_holdings_raw` gets its state from.

---

## 5. Template Sensor Design (Compute Layer)

This is the layer that turns "one JSON blob + N Yahoo Finance sensors" into everything the dashboards need.

### 5.1 `sensor.portfolio_holdings` — the master list

```yaml
# packages/investment/sensors_portfolio.yaml
template:
  - sensor:
      - name: "Portfolio Holdings"
        unique_id: portfolio_holdings
        state: "{{ states('input_text.portfolio_holdings_raw') | from_json | length }}"
        attributes:
          holdings: >
            {% set holdings = states('input_text.portfolio_holdings_raw') | from_json %}
            {% set ns = namespace(result=[]) %}
            {% for h in holdings %}
              {% set price_entity = 'sensor.yahoofinance_' ~ h.symbol | lower | replace('.', '_') %}
              {% set price = states(price_entity) | float(0) %}
              {% set market_value = price * h.shares %}
              {% set cost_basis = h.avg_price * h.shares %}
              {% set gain = market_value - cost_basis %}
              {% set gain_pct = (gain / cost_basis * 100) if cost_basis > 0 else 0 %}
              {% set ns.result = ns.result + [dict(h, **{
                   'price_entity': price_entity,
                   'current_price': price,
                   'market_value': market_value | round(2),
                   'cost_basis': cost_basis | round(2),
                   'unrealized_gain': gain | round(2),
                   'gain_pct': gain_pct | round(2),
                   'day_change_pct': state_attr(price_entity, 'regularMarketChangePercent') | float(0) | round(2)
                 }) ] %}
            {% endfor %}
            {{ ns.result }}
```

Every dashboard table (Portfolio, Allocation, Watchlist) reads `state_attr('sensor.portfolio_holdings', 'holdings')` — a ready-to-render list of dicts. Adding a metric means adding one key to that `dict(h, **{...})` block, once, for all assets.

### 5.2 `sensor.portfolio_summary` — the Overview KPIs

```yaml
  - sensor:
      - name: "Portfolio Summary"
        unique_id: portfolio_summary
        unit_of_measurement: "€"
        state: >
          {% set holdings = state_attr('sensor.portfolio_holdings', 'holdings') | default([]) %}
          {{ holdings | sum(attribute='market_value') | round(2) }}
        attributes:
          total_invested: >
            {{ (state_attr('sensor.portfolio_holdings','holdings') | default([]))
               | sum(attribute='cost_basis') | round(2) }}
          total_unrealized_gain: >
            {% set mv = state_attr('sensor.portfolio_holdings','holdings') | default([]) | sum(attribute='market_value') %}
            {% set cb = state_attr('sensor.portfolio_holdings','holdings') | default([]) | sum(attribute='cost_basis') %}
            {{ (mv - cb) | round(2) }}
          roi_pct: >
            {% set mv = state_attr('sensor.portfolio_holdings','holdings') | default([]) | sum(attribute='market_value') %}
            {% set cb = state_attr('sensor.portfolio_holdings','holdings') | default([]) | sum(attribute='cost_basis') %}
            {{ ((mv - cb) / cb * 100) | round(2) if cb > 0 else 0 }}
          cash_available: "{{ states('input_number.cash_available_eur') | float(0) }}"
          total_value_incl_cash: >
            {{ (state_attr('sensor.portfolio_holdings','holdings') | default([]) | sum(attribute='market_value'))
               + states('input_number.cash_available_eur') | float(0) }}
          last_update: "{{ now().isoformat() }}"
          market_open: >
            {# Simple US market-hours check; extend per-exchange if needed #}
            {% set t = now() %}
            {{ t.weekday() < 5 and 15 <= (t.hour + t.minute/60) <= 22 }}
```

Daily/weekly/monthly/YTD gain figures need a **reference point**, not just current state — see 5.3.

### 5.3 Time-based performance — `utility_meter` + `statistics` platform

Don't try to compute "gain since yesterday" from Jinja alone; Home Assistant already has purpose-built platforms for this:

```yaml
utility_meter:
  portfolio_value_daily:
    source: sensor.portfolio_summary
    cycle: daily
  portfolio_value_weekly:
    source: sensor.portfolio_summary
    cycle: weekly
  portfolio_value_monthly:
    source: sensor.portfolio_summary
    cycle: monthly
  portfolio_value_yearly:
    source: sensor.portfolio_summary
    cycle: yearly

sensor:
  - platform: statistics
    name: "Portfolio Value 24h Stats"
    entity_id: sensor.portfolio_summary
    state_characteristic: change
    max_age:
      hours: 24
```

Then a small template sensor turns the utility_meter deltas into %:

```yaml
template:
  - sensor:
      - name: "Portfolio Daily Change"
        unique_id: portfolio_daily_change_pct
        unit_of_measurement: "%"
        state: >
          {% set start = states('sensor.portfolio_value_daily') | float(0) %}
          {% set now_val = states('sensor.portfolio_summary') | float(0) %}
          {{ ((now_val - start) / start * 100) | round(2) if start > 0 else 0 }}
```

Repeat the pattern for weekly/monthly/YTD by pointing at the corresponding `utility_meter` entity. This gives you real historical baselines instead of fragile "last known value" hacks, and it's exactly how the Energy Dashboard itself computes daily/monthly consumption — consistent with your "comparable to the Energy Dashboard" goal.

### 5.4 Allocation sensors

```yaml
template:
  - sensor:
      - name: "Allocation Asset Class"
        unique_id: allocation_asset_class
        state: "ok"
        attributes:
          breakdown: >
            {% set holdings = state_attr('sensor.portfolio_holdings','holdings') | default([]) %}
            {% set total = holdings | sum(attribute='market_value') %}
            {% set types = holdings | map(attribute='type') | unique | list %}
            {% set ns = namespace(result=[]) %}
            {% for t in types %}
              {% set subtotal = holdings | selectattr('type','eq', t) | sum(attribute='market_value') %}
              {% set ns.result = ns.result + [{'label': t, 'value': subtotal | round(2),
                   'pct': (subtotal/total*100) | round(1) if total>0 else 0}] %}
            {% endfor %}
            {{ ns.result }}
```

The same pattern (group-by via `selectattr` + `unique`) covers currency allocation and, later, sector/geography once you add those fields to `holdings.yaml`.

### 5.5 Per-asset detail sensors — only where genuinely needed

For the Individual Asset Dashboard's 52-week high/low, market cap, dividend yield, and volume, use the Yahoo Finance sensor's own attributes directly rather than re-deriving them — the integration already exposes `fiftyTwoWeekHigh`, `fiftyTwoWeekLow`, `marketCap`, `trailingAnnualDividendYield`, and `regularMarketVolume` as attributes on `sensor.yahoofinance_<symbol>`. Reference them straight in the dashboard (Section 6.4) — no extra sensor required. This keeps the compute layer from growing 1:1 with assets, which is the whole point of this design.

---

## 6. Dashboard Layouts

All ten dashboards share one Lovelace view registered under a single sidebar entry with **tabs** (views), not ten separate dashboards — this matches how the Energy Dashboard presents multiple perspectives in one place and keeps navigation fast.

### 6.1 Overview

```yaml
# dashboards/investment/00_overview.yaml
title: Investments
views:
  - title: Overview
    path: overview
    icon: mdi:view-dashboard
    type: sections
    sections:
      - type: grid
        cards:
          - type: custom:mushroom-template-card
            primary: "Total Portfolio Value"
            secondary: "{{ states('sensor.portfolio_summary') }} €"
            icon: mdi:cash-multiple
            icon_color: blue

          - type: custom:mushroom-template-card
            primary: "Today"
            secondary: >
              {{ state_attr('sensor.portfolio_daily_change_pct','state') }}%
            icon: mdi:trending-up
            icon_color: >
              {{ 'green' if states('sensor.portfolio_daily_change') | float(0) >= 0 else 'red' }}

          - type: custom:mushroom-template-card
            primary: "ROI"
            secondary: "{{ state_attr('sensor.portfolio_summary','roi_pct') }}%"
            icon: mdi:percent
            icon_color: >
              {{ 'green' if state_attr('sensor.portfolio_summary','roi_pct')|float(0) >= 0 else 'red' }}

          - type: custom:mushroom-template-card
            primary: "Cash Available"
            secondary: "{{ state_attr('sensor.portfolio_summary','cash_available') }} €"
            icon: mdi:bank

      - type: grid
        cards:
          - type: custom:apexcharts-card
            header:
              title: Portfolio Value — Last 30 Days
              show: true
            graph_span: 30d
            series:
              - entity: sensor.portfolio_summary
                type: area
                name: Value

          - type: custom:mushroom-chips-card
            chips:
              - type: template
                icon: mdi:clock-outline
                content: "Updated {{ relative_time(as_datetime(state_attr('sensor.portfolio_summary','last_update'))) }} ago"
              - type: template
                icon: >
                  {{ 'mdi:circle' if state_attr('sensor.portfolio_summary','market_open') else 'mdi:circle-outline' }}
                icon_color: "{{ 'green' if state_attr('sensor.portfolio_summary','market_open') else 'grey' }}"
                content: >
                  {{ 'Market Open' if state_attr('sensor.portfolio_summary','market_open') else 'Market Closed' }}
```

### 6.2 Portfolio (holdings table)

```yaml
  - title: Portfolio
    path: portfolio
    icon: mdi:table
    cards:
      - type: custom:flex-table-card
        title: Holdings
        entities:
          include: sensor.portfolio_holdings
        columns:
          - name: Symbol
            data: holdings[].symbol
          - name: Name
            data: holdings[].name
          - name: Type
            data: holdings[].type
          - name: Shares
            data: holdings[].shares
          - name: Avg Price
            data: holdings[].avg_price
          - name: Current Price
            data: holdings[].current_price
          - name: Market Value
            data: holdings[].market_value
          - name: Gain %
            data: holdings[].gain_pct
            modify: >
              (x >= 0 ? '🟢 +' : '🔴 ') + x + '%'
        sort_by: "holdings[].market_value\\desc"
```

`flex-table-card` reads straight from the `holdings` attribute — no per-asset card. Conditional coloring is handled inline via the `modify` expression (emoji here; swap for a `card_mod` style rule if you want full background-color conditional formatting instead).

### 6.3 Allocation

```yaml
  - title: Allocation
    path: allocation
    icon: mdi:chart-pie
    cards:
      - type: custom:apexcharts-card
        header:
          title: Asset Class Allocation
        chart_type: donut
        series:
          - entity: sensor.allocation_asset_class
            data_generator: |
              return entity.attributes.breakdown.map((row) => {
                return [row.label, row.value];
              });
```

Duplicate this card block pointing at `sensor.allocation_currency` (once you add a matching sensor following the 5.4 pattern) for currency allocation, and so on for future sector/geography sensors — same card, different entity.

### 6.4 Individual Asset Detail (templated per-asset view)

```yaml
  - title: Asset Detail
    path: asset-detail
    icon: mdi:chart-line
    cards:
      - type: custom:mushroom-title-card
        title: "{{ states.sensor.yahoofinance_aapl.attributes.longName }}"

      - type: custom:mushroom-template-card
        primary: "{{ states('sensor.yahoofinance_aapl') }} USD"
        secondary: >
          {{ state_attr('sensor.yahoofinance_aapl','regularMarketChangePercent') }}%
        icon: mdi:apple

      - type: custom:apexcharts-card
        graph_span: 1d
        header:
          title: Intraday
        series:
          - entity: sensor.yahoofinance_aapl

      - type: custom:apexcharts-card
        header:
          title: Historical
          show_states: true
        graph_span: 1y
        series:
          - entity: sensor.yahoofinance_aapl

      - type: markdown
        content: >
          **52w High:** {{ state_attr('sensor.yahoofinance_aapl','fiftyTwoWeekHigh') }}
          **52w Low:** {{ state_attr('sensor.yahoofinance_aapl','fiftyTwoWeekLow') }}
          **Market Cap:** {{ state_attr('sensor.yahoofinance_aapl','marketCap') }}
          **Dividend Yield:** {{ state_attr('sensor.yahoofinance_aapl','trailingAnnualDividendYield') }}
          **Volume:** {{ state_attr('sensor.yahoofinance_aapl','regularMarketVolume') }}
```

For the 1D/5D/1M/6M/1Y/Max range selector, use ApexCharts' built-in period buttons instead of duplicating cards:

```yaml
      - type: custom:apexcharts-card
        graph_span: 1M
        header:
          show: true
          title: Price History
        experimental:
          color_threshold: true
        show:
          extrema: true
        span:
          start: day
        series:
          - entity: sensor.yahoofinance_aapl
        # ApexCharts supports a period-selector card-mod pattern;
        # simplest robust approach is 6 small chip buttons that each
        # call the same card via `graph_span` set through a dashboard
        # input_select + card templating.
```

**Practical note on the range selector:** ApexCharts-card doesn't have a native multi-button range switcher built in (unlike TradingView widgets). The clean way to get 1D/5D/1M/6M/1Y/Max in one card is an `input_select` helper (`input_select.asset_chart_range`) plus a `card-mod` style/`graph_span` bound to it, or simply six small `apexcharts-card` instances behind a `type: custom:tabbed-card` (or plain Lovelace tabs). I recommend the `input_select` + single dynamic card approach — one card, cheaper to render than six.

Because this view is per-symbol, **templating it 20 times by hand doesn't scale.** Two practical options once you have more than a handful of assets:
1. Keep one **generic** Asset Detail view with an `input_select` of your holdings' symbols at the top, and have every card reference `sensor.yahoofinance_{{ states('input_select.selected_asset') | lower }}` — this requires either a small Jinja-capable card (`custom:jinja-card`) or `browser_mod`/`config-template-card` since native Lovelace YAML can't runtime-select an entity_id inside static YAML.
2. Accept one dashboard **view per asset**, generated by a short Python/Jinja templating script you run locally whenever `holdings.yaml` changes (few lines, not part of HA itself) that expands a Jinja dashboard template into `dashboards/investment/03_asset_detail.yaml`.

Given your "minimal reconfiguration per new asset" requirement, **option 1** (config-template-card + input_select) is the better long-term fit and is what I'd implement first.

### 6.5 Market, Watchlist, Dividends, Performance, Goals, Analytics

These follow the same three building blocks already established, so I'm giving the pattern rather than repeating full YAML for each:

- **Market Dashboard**: one `sensor.market_<index>` per tracked index (S&P 500 = `^GSPC`, Nasdaq = `^IXIC`, VIX = `^VIX`, EUR/USD = `EURUSD=X`, Gold = `GC=F`, Bitcoin = `BTC-USD`) added as extra symbols in the same Yahoo Finance config entry — reuse the Individual Asset card pattern (6.4) in a grid, one small `apexcharts-card` + `mushroom-template-card` per index.
- **Watchlist Dashboard**: identical structure to `holdings.yaml`/`sensor.portfolio_holdings` (Section 4–5.1) but a second `input_text.watchlist_raw` + `sensor.watchlist_items`, adding `target_price` and computing `distance_pct = (current - target) / target * 100`. Render with the same `flex-table-card` pattern as 6.2.
- **Dividend Dashboard**: Yahoo Finance exposes `dividendDate` and `trailingAnnualDividendRate` per symbol; aggregate them in a `sensor.dividend_summary` template sensor using the same for-loop pattern as 5.1, summing `shares * trailingAnnualDividendRate` across holdings for "expected annual income." Upcoming payments render via `auto-entities` filtered on `dividendDate` within the next 30 days.
- **Performance Dashboard**: entirely served by the `utility_meter` + `statistics` sensors from 5.3, plus HA's built-in **long-term statistics** (Developer Tools → Statistics) graphed via `apexcharts-card` with `statistics: true` for cumulative/rolling views over months or years without recorder bloat.
- **Goals Dashboard**: `input_number.goal_portfolio_target` vs `sensor.portfolio_summary` rendered as a `mushroom-template-card` with a progress bar (`bar-card` is a nice optional HACS addition here), plus a simple linear projection template sensor: `estimated_completion = goal / (current_growth_rate_per_month)`.
- **Analytics Dashboard**: CAGR, volatility, and best/worst performer are all one-more-Jinja-block additions to `sensor.portfolio_holdings`/`sensor.portfolio_summary` (e.g. `holdings | max(attribute='gain_pct')` for best performer) — no new architecture needed, just extending the existing templates.

---

## 7. Automations

```yaml
# packages/investment/automations.yaml
automation:
  - alias: "Investment: Daily Portfolio Summary"
    trigger:
      - platform: time
        at: "22:15:00"
    condition:
      - condition: state
        entity_id: binary_sensor.market_hours  # optional helper you can add
        state: "off"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Portfolio Summary"
          message: >
            Value: {{ states('sensor.portfolio_summary') }} €
            Today: {{ state_attr('sensor.portfolio_daily_change_pct','state') }}%
            ROI: {{ state_attr('sensor.portfolio_summary','roi_pct') }}%

  - alias: "Investment: Asset Move Alert"
    trigger:
      - platform: template
        value_template: >
          {% set holdings = state_attr('sensor.portfolio_holdings','holdings') | default([]) %}
          {{ holdings | selectattr('day_change_pct','defined')
                       | selectattr('day_change_pct','lt', -5) | list | count > 0 }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "⚠️ Asset Alert"
          message: "One or more holdings moved more than 5% today. Check the Portfolio dashboard."

  - alias: "Investment: Allocation Drift Alert"
    trigger:
      - platform: time_pattern
        hours: "/6"
    condition:
      - condition: template
        value_template: >
          {% set b = state_attr('sensor.allocation_asset_class','breakdown') | default([]) %}
          {% set stocks = b | selectattr('label','eq','stock') | map(attribute='pct') | first | default(0) %}
          {{ stocks > 70 or stocks < 40 }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Stock allocation has drifted outside your 40–70% target band."

  - alias: "Investment: Missing Price Data Alert"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.portfolio_holdings','holdings')
             | selectattr('current_price','eq', 0) | list | count > 0 }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Portfolio Data Issue"
          message: "One or more Yahoo Finance sensors returned no price. Check Settings → Devices & Services → Yahoo Finance."

  - alias: "Investment: Portfolio Milestone Reached"
    trigger:
      - platform: numeric_state
        entity_id: sensor.portfolio_summary
        above: input_number.goal_portfolio_target
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🎉 Goal Reached"
          message: "Your portfolio has passed your target of {{ states('input_number.goal_portfolio_target') }} €."
```

Weekly/monthly report automations reuse the same `notify` pattern on `time` triggers with `weekday`/`day` conditions, pulling from the `utility_meter` weekly/monthly entities instead of daily.

---

## 8. Scalability Recommendations

1. **Never create a template sensor per asset for a metric that can live in a shared list-attribute.** Every dashboard here reads `holdings`/`breakdown` attributes, not entity lists — this is what lets the config stay flat as your portfolio grows from 5 to 50 positions.
2. **Keep `holdings.yaml`/`input_text` as the only place you add assets**, and pair every addition with adding the same symbol to the Yahoo Finance integration's options (that part currently can't be avoided — HA integrations don't support wildcard symbol discovery).
3. **Cap Jinja loop cost.** The for-loops in Section 5 run on every state change of any input. With 373 existing entities and growing, set `scan_interval`-equivalent behavior by triggering recompute only on relevant events — template sensors already do this automatically (they re-evaluate only when a referenced entity changes), so this is handled for you as long as you don't reference unrelated entities inside these templates.
4. **Group future dimensions (sector, geography) as extra keys in `holdings.yaml`**, not new files — the allocation sensor pattern (5.4) already generalizes to any field via `selectattr`.
5. **When you exceed ~50–60 holdings**, migrate `input_text` → a `file` sensor reading local JSON, and consider moving the heaviest Jinja aggregation into a small **pyscript** function — same entity surface, just faster computation, so dashboards don't need to change.

---

## 9. Performance Optimization

- **Limit `apexcharts-card` `graph_span`** on dashboards that don't need it (e.g. Overview needs 30 days, not "max") — long spans pull more recorder/statistics data and slow dashboard load.
- **Use HA long-term statistics, not raw recorder history**, for anything beyond ~10 days of chart data (`apexcharts-card` supports `statistics: true` per series) — the recorder purges raw history after your configured `purge_keep_days` (commonly 10), but statistics persist indefinitely at hourly/daily resolution, which is what you actually want for YTD/1Y/Max charts.
- **Set a sensible `recorder:` `exclude`** for the high-churn helper entities (`input_text.portfolio_holdings_raw` itself doesn't need history) to keep the database lean:
  ```yaml
  recorder:
    exclude:
      entities:
        - input_text.portfolio_holdings_raw
        - input_text.watchlist_raw
  ```
- **Yahoo Finance polling interval**: the integration defaults to a conservative refresh; don't set it below a few minutes — intraday granularity beyond that adds load without adding real insight for a personal dashboard, and can risk rate-limiting.
- **Avoid nesting `flex-table-card`/`auto-entities` inside `apexcharts-card` custom cards or vice versa** — keep each card reading directly off the compute-layer sensors described in Section 5 rather than off each other, so a slow render in one card doesn't cascade.

---

## 10. Best Practices for Future Expansion

- **Sector/Geography allocation** (marked "future" in your spec): add `sector` and `region` keys to each `holdings.yaml` entry now, even if left blank — the allocation sensor pattern already handles arbitrary grouping keys, so this becomes a zero-architecture-change addition later.
- **Benchmark comparison / Sharpe ratio / max drawdown** (marked "potential future" for Analytics): these need a stored daily value series, which the `utility_meter` sensors from 5.3 already start building. Once you have several months of history in long-term statistics, these are pure math over `sensor.portfolio_summary`'s statistics table — no new data collection needed, just new template sensors reading `statistics` via the `recorder` history stats platform.
- **Multi-currency support**: keep `currency` as a required field per holding now (already included above) even if everything today is EUR/USD — retrofitting currency conversion later (via an `ExchangeRate` sensor from Yahoo Finance, e.g. `EURUSD=X`) is then a one-line multiplier added to the existing Jinja loop, not a redesign.
- **Version-control your `packages/investment/` folder** (git, or at minimum HA's built-in backup) — since your entire investment config is now a handful of YAML files rather than scattered UI-created helpers, it's fully diffable and restorable.
- **Document the schema** of `holdings.yaml` in a comment block at its top (fields, required vs optional, valid `type` values) so future-you (or anyone else touching the config) doesn't need to reverse-engineer the Jinja to know what's expected.

---

## 11. Immediate Next Steps

1. Restart Home Assistant to clear the pending Yahoo Finance HACS repair.
2. Install `mushroom`, `auto-entities`, and `flex-table-card` via HACS → Frontend (you already have `apexcharts-card`).
3. Configure the Yahoo Finance integration (Settings → Devices & Services → Add Integration) with your actual holding + index symbols.
4. Create `packages/investment/` and drop in `holdings.yaml`, `sensors_portfolio.yaml`, `helpers.yaml` from Sections 4–5, adapted to your real holdings.
5. Add the `packages:` line to `configuration.yaml`, then **Developer Tools → YAML → Reload Template Entities** (no restart needed) to verify `sensor.portfolio_holdings` and `sensor.portfolio_summary` populate correctly.
6. Build the Overview dashboard (Section 6.1) first — it's the fastest way to confirm the whole compute chain works end-to-end — then layer in the remaining nine views.

If you'd like, I can now write out the actual `holdings.yaml` and `sensors_portfolio.yaml` files pre-filled with your real symbols and share counts, or generate the full first dashboard YAML file ready to drop into `dashboards/investment/00_overview.yaml`.
