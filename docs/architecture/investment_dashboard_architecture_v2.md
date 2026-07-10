# Home Assistant Investment Dashboard — Revised Architecture (v2)

This supersedes the v1 document. The core change: calculation logic moves out of Jinja templates and into a small **custom integration** ("Portfolio Engine") written in Python. That's the only realistic way to satisfy all four of your hard requirements simultaneously — true separation of concerns, provider independence, scale to hundreds of assets, and something that "resembles a well-designed integration" rather than a stack of template sensors.

I'll explain why Jinja-only doesn't survive that combination, then give you the full three-layer design.

## 0. Why this needs a custom component, not just packages/templates

The v1 design (Jinja for-loops over an `input_text` blob) works fine for a few dozen holdings. It stops being appropriate once you apply your new constraints together:

- **"Dashboards should never calculate, single source of truth for calculations"** — Jinja templates embedded in `template:` sensors *are* calculation logic living inside YAML config, which is really the same layer-mixing problem one level up. A `sensor:` block with 40 lines of Jinja is not meaningfully more "engine-like" than a dashboard card doing the same math.
- **"Dozens or hundreds of assets"** — every `template` sensor re-evaluates its Jinja on every relevant state change, synchronously, on the event loop. A 200-line Jinja loop over 200 holdings recalculating allocation/sector/currency breakdowns on *every single price tick* is exactly the kind of thing that causes template sensors to show up in HA's slow-template warnings.
- **"Provider independence, minimal changes to swap providers"** — Jinja has no clean way to express "try provider A, fall back to provider B" or "normalize three different API response shapes into one internal `Quote` model." That's an abstraction problem, and Python classes are the right tool, not template macros.
- **"Resemble a well-designed integration"** — this is a direct request for `custom_components/`, not more packages.

So: **Tier 1 (recommended, this document)** is a small custom component that owns ingestion + calculation. **Tier 2 (fallback)** is the v1 YAML/Jinja approach, kept only as a low-effort starting point if you'd rather not touch Python yet — I've noted where it still applies below, but everything else in this document assumes Tier 1.

---

## 1. Three-Layer Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA                                                   │
│  /config/investments/*.yaml — pure user-entered configuration.    │
│  No calculated fields. No provider-specific fields.                │
└───────────────────────────┬─────────────────────────────────────┘
                            │ loaded + watched for changes
┌───────────────────────────▼─────────────────────────────────────┐
│  LAYER 2 — CALCULATION  (custom_components/portfolio_engine/)     │
│  ┌───────────────┐   ┌────────────────┐   ┌────────────────────┐│
│  │ Provider       │   │ DataUpdate      │   │ PortfolioEngine    ││
│  │ abstraction    │──▶│ Coordinator     │──▶│ (pure Python calc) ││
│  │ (ABC + impls)  │   │ (fetch/schedule)│   │ value/gain/ROI/    ││
│  │                │   │                 │   │ allocation/sector/ ││
│  │ yahoo_finance  │   │                 │   │ dividends/hist.    ││
│  │ finnhub (stub) │   │                 │   │                    ││
│  │ csv_import     │   │                 │   │                    ││
│  └───────────────┘   └────────────────┘   └──────────┬─────────┘│
│                                                        │ engine    │
│                                             ┌──────────▼─────────┐│
│                                             │ sensor.py —         ││
│                                             │ dedicated entities  ││
│                                             │ + attribute-rich    ││
│                                             │ list entities       ││
│                                             └──────────┬─────────┘│
└────────────────────────────────────────────────────────┼─────────┘
                                                          │ entities
┌─────────────────────────────────────────────────────────▼────────┐
│  LAYER 3 — PRESENTATION  (/config/dashboards/investments/*.yaml)  │
│  Overview · Portfolio · Holdings · Allocation · Markets ·          │
│  Performance · Dividends · Watchlist · Goals · Analytics · Settings│
│  Reads entities/attributes only. Zero calculation.                │
└─────────────────────────────────────────────────────────────────┘
```

**Rule enforced by this structure, not just convention:** Layer 3 files physically cannot contain calculation, because Lovelace YAML has no computation model beyond simple Jinja in `markdown`/`template` cards — and this design gives every dashboard a ready-made entity or attribute for anything it needs, so there's never a reason to write Jinja math in a card. If a dashboard *would* need to compute something, that's a signal the engine is missing a field — add it in Layer 2, not Layer 3.

---

## 2. Layer 1 — Data (pure, provider-agnostic)

### 2.1 Folder structure

```
/config/investments/
├── holdings.yaml
├── watchlist.yaml
├── markets.yaml
├── sectors.yaml          # optional lookup table: symbol → sector/region, for assets where the provider doesn't supply it
└── settings.yaml
```

### 2.2 `holdings.yaml` — only what a human types in

```yaml
# /config/investments/holdings.yaml
# Schema: symbol (str, required) · name (str, optional — engine fetches if omitted)
# shares (float, required) · avg_price (float, required) · currency (str, ISO 4217, required)
# type (str: stock|etf|fund|crypto|cash, required) · account (str, optional, for future multi-account support)
# NO calculated fields belong here. Ever.

holdings:
  - symbol: AAPL
    shares: 12
    avg_price: 165.20
    currency: USD
    type: stock

  - symbol: VWCE.DE
    shares: 40
    avg_price: 105.10
    currency: EUR
    type: etf

  - symbol: MSFT
    shares: 8
    avg_price: 310.00
    currency: USD
    type: stock

  - symbol: BTC-USD
    shares: 0.15
    avg_price: 42000.00
    currency: USD
    type: crypto
```

### 2.3 `watchlist.yaml`

```yaml
watchlist:
  - symbol: NVDA
    target_price: 850.00
    currency: USD

  - symbol: TSLA
    target_price: 180.00
    currency: USD
```

### 2.4 `markets.yaml`

```yaml
markets:
  - symbol: "^GSPC"
    label: "S&P 500"
  - symbol: "^IXIC"
    label: "Nasdaq"
  - symbol: "^DJI"
    label: "Dow Jones"
  - symbol: "^STOXX50E"
    label: "Euro Stoxx 50"
  - symbol: "^VIX"
    label: "VIX"
  - symbol: "EURUSD=X"
    label: "EUR/USD"
  - symbol: "GC=F"
    label: "Gold"
  - symbol: "BTC-USD"
    label: "Bitcoin"
```

### 2.5 `sectors.yaml` (optional override/lookup)

Only needed for symbols where your chosen provider doesn't return sector/region — a manual override table, not a cache of calculated data:

```yaml
overrides:
  VWCE.DE:
    sector: "Diversified"
    region: "Global"
```

### 2.6 `settings.yaml` — engine configuration, not portfolio data

```yaml
settings:
  base_currency: EUR
  provider: yahoo_finance          # swap this one line to change data source
  update_interval_minutes: 15
  market_hours_provider: yahoo_finance
  alert_thresholds:
    single_asset_move_pct: 5
    allocation_drift_pct: 15
  goals:
    portfolio_target: 250000
    monthly_contribution: 1000
```

This is the file the Settings dashboard (Section 5) edits. Note it lives in the *data* layer, not the calculation layer — it's still just user-entered configuration, the engine reads it the same way it reads holdings.

---

## 3. Layer 2 — Calculation (`custom_components/portfolio_engine/`)

### 3.1 File structure

```
custom_components/portfolio_engine/
├── __init__.py            # setup, loads /config/investments/*.yaml, starts coordinator
├── manifest.json
├── const.py
├── coordinator.py         # DataUpdateCoordinator — scheduling, batching, error handling
├── engine.py              # PortfolioEngine — pure calculation, no HA imports, unit-testable
├── models.py              # dataclasses: Quote, Holding, PortfolioSnapshot
├── sensor.py              # entity creation from coordinator data
└── providers/
    ├── __init__.py
    ├── base.py             # PriceProvider ABC
    ├── yahoo_finance.py    # wraps yfinance or reuses the HACS integration's data
    ├── finnhub.py          # stub, same interface
    └── csv_import.py       # offline/manual pricing fallback
```

This is a real `custom_components` folder — HACS-installable, versioned, restart-loaded like any other integration. It's a bigger lift than packages, but it's what actually satisfies "resembles a well-designed integration."

### 3.2 Provider abstraction — this is what buys you provider independence

```python
# custom_components/portfolio_engine/models.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Quote:
    symbol: str
    price: float
    currency: str
    change_pct: float
    day_high: float | None = None
    day_low: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    market_cap: float | None = None
    dividend_yield: float | None = None
    dividend_rate: float | None = None
    volume: int | None = None
    name: str | None = None
    sector: str | None = None
    region: str | None = None
    as_of: datetime | None = None
```

```python
# custom_components/portfolio_engine/providers/base.py
from abc import ABC, abstractmethod
from ..models import Quote

class PriceProvider(ABC):
    """Every data source implements this. The engine only ever talks to this interface."""

    @abstractmethod
    async def async_get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Return a symbol -> Quote map. Must batch internally where the provider supports it."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def supports_market_hours(self) -> bool:
        return False

    async def async_get_market_hours(self, symbol: str) -> bool | None:
        return None
```

```python
# custom_components/portfolio_engine/providers/yahoo_finance.py
from .base import PriceProvider
from ..models import Quote
import aiohttp

class YahooFinanceProvider(PriceProvider):
    name = "yahoo_finance"

    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    async def async_get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        # Batch call — Yahoo's quote endpoint accepts comma-separated symbols,
        # so hundreds of holdings still cost one HTTP round trip, not N.
        joined = ",".join(symbols)
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={joined}"
        async with self._session.get(url) as resp:
            data = await resp.json()
        results = {}
        for item in data["quoteResponse"]["result"]:
            results[item["symbol"]] = Quote(
                symbol=item["symbol"],
                price=item.get("regularMarketPrice", 0),
                currency=item.get("currency", "USD"),
                change_pct=item.get("regularMarketChangePercent", 0),
                day_high=item.get("regularMarketDayHigh"),
                day_low=item.get("regularMarketDayLow"),
                week52_high=item.get("fiftyTwoWeekHigh"),
                week52_low=item.get("fiftyTwoWeekLow"),
                market_cap=item.get("marketCap"),
                dividend_yield=item.get("trailingAnnualDividendYield"),
                dividend_rate=item.get("trailingAnnualDividendRate"),
                volume=item.get("regularMarketVolume"),
                name=item.get("longName") or item.get("shortName"),
            )
        return results
```

Adding Finnhub, Alpha Vantage, Twelve Data, Polygon, or a broker API later means writing one more file that implements the same four methods — **nothing else in the project changes.** Swapping providers is the one-line `provider: yahoo_finance` → `provider: finnhub` edit in `settings.yaml` your requirement asked for.

> Note on your existing HACS Yahoo Finance integration: you can either (a) have `YahooFinanceProvider` call the Yahoo HTTP endpoint directly as shown (recommended — keeps the engine self-contained and not dependent on another integration's entity naming), or (b) have it read `sensor.yahoofinance_*` state/attributes if you'd rather keep using that integration for ingestion. (a) is cleaner for provider-independence since it doesn't tie your engine's data path to a second integration's lifecycle; I'd migrate off the HACS integration once the engine is running and decommission it to avoid duplicate API calls.

### 3.3 The engine — pure calculation, zero Home Assistant imports

This is the actual "single source of truth." It's plain Python, unit-testable without spinning up HA at all.

```python
# custom_components/portfolio_engine/engine.py
from dataclasses import dataclass
from .models import Quote

@dataclass
class HoldingResult:
    symbol: str
    name: str
    type: str
    currency: str
    shares: float
    avg_price: float
    current_price: float
    market_value: float
    market_value_base: float   # converted to base_currency
    cost_basis: float
    unrealized_gain: float
    gain_pct: float
    day_change_pct: float
    sector: str | None
    region: str | None

class PortfolioEngine:
    def __init__(self, base_currency: str, fx_rates: dict[str, float]):
        self.base_currency = base_currency
        self.fx_rates = fx_rates  # e.g. {"USD": 0.92} meaning 1 USD = 0.92 base units

    def _to_base(self, amount: float, currency: str) -> float:
        if currency == self.base_currency:
            return amount
        return amount * self.fx_rates.get(currency, 1.0)

    def calculate_holdings(self, holdings: list[dict], quotes: dict[str, Quote],
                            sector_overrides: dict[str, dict]) -> list[HoldingResult]:
        results = []
        for h in holdings:
            q = quotes.get(h["symbol"])
            price = q.price if q else 0.0
            market_value = price * h["shares"]
            cost_basis = h["avg_price"] * h["shares"]
            gain = market_value - cost_basis
            override = sector_overrides.get(h["symbol"], {})
            results.append(HoldingResult(
                symbol=h["symbol"],
                name=(q.name if q and q.name else h.get("name", h["symbol"])),
                type=h["type"],
                currency=h["currency"],
                shares=h["shares"],
                avg_price=h["avg_price"],
                current_price=price,
                market_value=round(market_value, 2),
                market_value_base=round(self._to_base(market_value, h["currency"]), 2),
                cost_basis=round(cost_basis, 2),
                unrealized_gain=round(gain, 2),
                gain_pct=round((gain / cost_basis * 100) if cost_basis else 0, 2),
                day_change_pct=round(q.change_pct, 2) if q else 0.0,
                sector=override.get("sector") or (q.sector if q else None),
                region=override.get("region") or (q.region if q else None),
            ))
        return results

    def calculate_summary(self, results: list[HoldingResult], cash_base: float) -> dict:
        total_value = sum(r.market_value_base for r in results)
        total_cost = sum(self._to_base(r.cost_basis, r.currency) for r in results)
        return {
            "total_value": round(total_value, 2),
            "total_invested": round(total_cost, 2),
            "total_unrealized_gain": round(total_value - total_cost, 2),
            "roi_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost else 0,
            "cash_balance": round(cash_base, 2),
            "total_value_incl_cash": round(total_value + cash_base, 2),
        }

    def calculate_allocation(self, results: list[HoldingResult], group_by: str) -> list[dict]:
        total = sum(r.market_value_base for r in results) or 1
        groups: dict[str, float] = {}
        for r in results:
            key = getattr(r, group_by) or "Unclassified"
            groups[key] = groups.get(key, 0) + r.market_value_base
        return [
            {"label": k, "value": round(v, 2), "pct": round(v / total * 100, 1)}
            for k, v in sorted(groups.items(), key=lambda kv: -kv[1])
        ]

    def best_worst(self, results: list[HoldingResult]) -> dict:
        if not results:
            return {"best": None, "worst": None}
        best = max(results, key=lambda r: r.gain_pct)
        worst = min(results, key=lambda r: r.gain_pct)
        return {"best": best.symbol, "best_pct": best.gain_pct,
                "worst": worst.symbol, "worst_pct": worst.gain_pct}
```

`calculate_allocation` takes a `group_by` field name (`"type"`, `"sector"`, `"region"`, `"currency"`) so asset class / sector / country / currency allocation are all the same function — this is the Python equivalent of the `selectattr`/`unique` pattern from v1, just fast and testable instead of re-parsed Jinja.

### 3.4 Coordinator — scheduling and batching

```python
# custom_components/portfolio_engine/coordinator.py
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .engine import PortfolioEngine

class PortfolioCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, provider, engine: PortfolioEngine, data_layer):
        super().__init__(
            hass, logger=..., name="portfolio_engine",
            update_interval=timedelta(minutes=data_layer.settings["update_interval_minutes"]),
        )
        self.provider = provider
        self.engine = engine
        self.data_layer = data_layer

    async def _async_update_data(self):
        holdings = self.data_layer.holdings
        watchlist = self.data_layer.watchlist
        markets = self.data_layer.markets
        symbols = list({h["symbol"] for h in holdings}
                        | {w["symbol"] for w in watchlist}
                        | {m["symbol"] for m in markets})
        quotes = await self.provider.async_get_quotes(symbols)   # ONE batched call for all symbols

        results = self.engine.calculate_holdings(holdings, quotes, self.data_layer.sector_overrides)
        summary = self.engine.calculate_summary(results, self.data_layer.cash_balance)
        allocations = {
            dim: self.engine.calculate_allocation(results, dim)
            for dim in ("type", "sector", "region", "currency")
        }
        return {
            "holdings": results,
            "summary": summary,
            "allocations": allocations,
            "best_worst": self.engine.best_worst(results),
            "watchlist": self._calc_watchlist(watchlist, quotes),
            "markets": self._calc_markets(markets, quotes),
        }
```

**This is the scalability answer for hundreds of assets:** one coordinator refresh = one batched provider call (Yahoo's quote endpoint accepts hundreds of symbols per request) + one pass of pure-Python calculation over an in-memory list, on a background executor — not hundreds of independent template re-evaluations firing on the event loop every time any single price changes. You control the pace entirely via `update_interval_minutes` in `settings.yaml`.

### 3.5 Sensor platform — the hybrid entity model

```python
# custom_components/portfolio_engine/sensor.py
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class PortfolioValueSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Portfolio Value"
    _attr_unique_id = "portfolio_engine_value"
    _attr_native_unit_of_measurement = None  # set to base_currency at runtime

    @property
    def native_value(self):
        return self.coordinator.data["summary"]["total_value"]

class PortfolioDailyGainSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Portfolio Daily Gain"
    _attr_unique_id = "portfolio_engine_daily_gain"
    # backed by a `utility_meter`-style helper the engine maintains internally,
    # OR delegate day-over-day delta to HA's own long-term statistics on
    # PortfolioValueSensor (recommended — one less thing for the engine to own)

class PortfolioHoldingsSensor(CoordinatorEntity, SensorEntity):
    """List-valued attribute entity — this is where the 'attributes for display data' rule applies."""
    _attr_name = "Portfolio Holdings"
    _attr_unique_id = "portfolio_engine_holdings"

    @property
    def native_value(self):
        return len(self.coordinator.data["holdings"])

    @property
    def extra_state_attributes(self):
        return {"holdings": [vars(h) for h in self.coordinator.data["holdings"]]}
```

**Dedicated sensors** (per your requirement — frequently displayed, used in automations, need statistics, used in charts):

| Entity | Purpose |
|---|---|
| `sensor.portfolio_value` | headline KPI, chart source, automation trigger source |
| `sensor.portfolio_daily_gain` | automations, Overview KPI |
| `sensor.portfolio_total_profit` | Overview KPI, chart |
| `sensor.portfolio_total_invested` | Overview KPI |
| `sensor.portfolio_cash_balance` | Overview KPI, Goals |
| `sensor.portfolio_roi` | Overview/Analytics KPI |
| `sensor.portfolio_dividend_income_ytd` | Dividends KPI, automations |

**Attribute-only entities** (display-heavy, list-shaped, not individually needed in automations):

| Entity | Attribute | Used by |
|---|---|---|
| `sensor.portfolio_holdings` | `holdings: [...]` | Portfolio, Holdings dashboards |
| `sensor.portfolio_allocation` | `by_type`, `by_sector`, `by_region`, `by_currency` | Allocation dashboard |
| `sensor.portfolio_watchlist` | `items: [...]` | Watchlist dashboard |
| `sensor.portfolio_markets` | `indices: [...]` | Markets dashboard |
| `sensor.portfolio_dividends` | `upcoming: [...]`, `history: [...]` | Dividends dashboard |

This is precisely your hybrid model: entities where HA's own strengths (history graphs, automation triggers, `numeric_state` conditions) genuinely add value, attributes everywhere the data is purely for rendering a list or table.

---

## 4. Layer 3 — Presentation

### 4.1 Folder structure (as you specified)

```
/config/dashboards/investments/
├── overview.yaml
├── portfolio.yaml
├── holdings.yaml
├── allocation.yaml
├── markets.yaml
├── watchlist.yaml
├── dividends.yaml
├── analytics.yaml
├── goals.yaml
└── settings.yaml
```

Each is a Lovelace **view** (not a separate top-level dashboard) assembled into one dashboard via `!include`, so navigation stays a single sidebar entry with tabs:

```yaml
# top-level dashboard config
title: Investments
views:
  - !include dashboards/investments/overview.yaml
  - !include dashboards/investments/portfolio.yaml
  - !include dashboards/investments/holdings.yaml
  - !include dashboards/investments/allocation.yaml
  - !include dashboards/investments/markets.yaml
  - !include dashboards/investments/watchlist.yaml
  - !include dashboards/investments/dividends.yaml
  - !include dashboards/investments/goals.yaml
  - !include dashboards/investments/analytics.yaml
  - !include dashboards/investments/settings.yaml
```

Note the distinction between **Portfolio** and **Holdings** you asked for: `portfolio.yaml` is the KPI/summary-oriented page (uses the dedicated sensors — value, gain, ROI, allocation donut); `holdings.yaml` is the raw sortable/filterable table of every position (uses `sensor.portfolio_holdings`'s attribute via `flex-table-card`, exactly as in v1 Section 6.2, just renamed to match your structure).

### 4.2 Every card now has exactly one job: bind to an entity/attribute

```yaml
# dashboards/investments/portfolio.yaml
title: Portfolio
path: portfolio
cards:
  - type: custom:mushroom-template-card
    primary: Total Value
    secondary: "{{ states('sensor.portfolio_value') }} {{ state_attr('sensor.portfolio_value','unit_of_measurement') }}"
    icon: mdi:cash-multiple

  - type: custom:mushroom-template-card
    primary: Today
    secondary: "{{ states('sensor.portfolio_daily_gain') }}%"
    icon_color: "{{ 'green' if states('sensor.portfolio_daily_gain')|float(0) >= 0 else 'red' }}"

  - type: custom:apexcharts-card
    header: {title: Portfolio Value, show: true}
    graph_span: 30d
    series:
      - entity: sensor.portfolio_value
        statistics: true
```

No Jinja loops, no `selectattr`, no math — every value is a direct entity or attribute reference. If a dashboard designer ever needs to add a `{% for %}` to a card, that's the signal to go add a field to `engine.py` instead.

### 4.3 Settings dashboard — new addition

```yaml
# dashboards/investments/settings.yaml
title: Settings
path: settings
cards:
  - type: entities
    title: Engine Configuration
    entities:
      - entity: input_select.portfolio_provider
        name: Data Provider
      - entity: input_number.portfolio_update_interval
        name: Update Interval (minutes)
      - entity: input_number.portfolio_alert_threshold_pct
        name: Single-Asset Move Alert (%)
      - entity: input_number.goal_portfolio_target
        name: Portfolio Target
      - entity: input_number.goal_monthly_contribution
        name: Monthly Contribution Target
```

These `input_*` helpers are a thin editable mirror of `settings.yaml` — the engine's config entry (or a small options flow, if you add one later) reads them and writes back to `/config/investments/settings.yaml`, or simply reads the helpers directly as its live config source instead of the YAML file, your choice. Either way, the Settings *dashboard* only displays/edits — it doesn't recalculate anything, consistent with Layer 3's rule.

---

## 5. Scalability at "hundreds of assets"

| Concern | v1 (Jinja/packages) | v2 (custom component) |
|---|---|---|
| Recalculation trigger | Any referenced entity changes → full Jinja re-run | One coordinator tick on your schedule, batched |
| Provider calls for 200 symbols | 200 individual `sensor.yahoofinance_*` entities (200 HTTP calls, integration-managed) | 1 batched call via `PriceProvider.async_get_quotes(all_symbols)` |
| Allocation by 4 dimensions | 4 separate Jinja blocks, each re-parsing the full holdings list | 1 Python function called 4 times over an already-in-memory list |
| Adding a computed field | Edit Jinja in a `template:` sensor, restart/reload | Add one field to `HoldingResult`, reload integration |
| Table rendering (200 rows) | `flex-table-card` reading a 200-item Jinja-built attribute (fine) | Same, but the attribute is built once per coordinator tick instead of once per template re-render |
| Testability | None — Jinja can't be unit tested | `engine.py` has zero HA imports; plain `pytest` covers it |

Practical scale guidance either way:
- Table cards (`flex-table-card`) should paginate or default-filter (e.g. top 20 by value, with a "show all" toggle) once holdings exceed ~100 rows, purely for browser rendering performance — this is a Lovelace concern, unrelated to the engine.
- Long-term statistics (Section 9 of v1, still applicable) remain the right way to store history — the coordinator only needs to hold *current* state in memory; HA's recorder/statistics tables handle everything historical.

---

## 6. Provider Independence — summary

To switch from Yahoo Finance to, say, Twelve Data:

1. Write `providers/twelve_data.py` implementing `PriceProvider` (one file, same four methods as `yahoo_finance.py`).
2. Change `provider: yahoo_finance` to `provider: twelve_data` in `settings.yaml` (or the Settings dashboard's `input_select`).
3. Reload the integration.

Nothing in `engine.py`, `sensor.py`, or any dashboard file changes — they all consume the provider-agnostic `Quote` model and the engine's output, never the raw provider response shape.

---

## 7. Migration Path from v1

If you already started on the v1 packages/Jinja approach, you don't need to throw it away to get here:

1. Build `custom_components/portfolio_engine/` alongside the existing packages (they don't conflict — different entity IDs).
2. Point new dashboard views at the new engine's entities.
3. Once verified, delete `packages/investment/sensors_*.yaml` and the `input_text.portfolio_holdings_raw` helper — the engine's `holdings.yaml` loader replaces both.
4. Decommission the HACS Yahoo Finance integration once `YahooFinanceProvider` is confirmed working, to avoid two things polling the same API.

---

## 8. What I'd build first

Given this is now a real integration rather than YAML packages, I'd sequence it as:

1. `models.py`, `providers/base.py`, `providers/yahoo_finance.py` — get one batched quote call working, tested standalone (even a throwaway script, before touching HA).
2. `engine.py` with unit tests against fixed sample data — verify the math before it's live.
3. `coordinator.py` + minimal `__init__.py` — wire it into HA, confirm `hass.data` populates on an interval.
4. `sensor.py` — dedicated sensors first (Section 3.5 table), then the attribute-list sensors.
5. `overview.yaml` and `portfolio.yaml` dashboards to validate end-to-end.
6. Remaining dashboard views, then `watchlist`/`markets` support in the coordinator, then dividends/goals/analytics.

I can write out a working first pass of `models.py`, `providers/base.py`, `providers/yahoo_finance.py`, and `engine.py` as actual files (not just the skeletons above) if you'd like to start from real code rather than a spec — that's probably the highest-value next step given how much of this design now lives in Python rather than YAML.
