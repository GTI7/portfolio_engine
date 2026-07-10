# Home Assistant Investment Dashboard — Architecture v3 (Production Integration Design)

This supersedes v2. Every point from your feedback is addressed below. The honest framing up front: this turns the project from "a custom component" into "a small, real financial application that happens to run inside Home Assistant." That's the right call given where your requirements have converged (multi-portfolio, transaction history, tax-adjacent reporting, broker integrations) — but it means the build is now sequenced in milestones (Section 11), not something to write in one pass. Treat this document as the target architecture, not a one-shot implementation.

---

## 1. Home Assistant Conventions

| Convention | How it's applied |
|---|---|
| `DataUpdateCoordinator` for all polling | One coordinator per portfolio's price-refresh cycle (Section 6); a second, longer-interval coordinator for FX rates (Section 3), since currency pairs change less often than equity prices and shouldn't share a poll cycle. |
| `ConfigEntry` + `OptionsFlow` | Initial setup (provider choice, base currency, first portfolio) via `config_flow.py`. Ongoing tuning (update interval, alert thresholds, adding/removing portfolios) via `OptionsFlow` so it's editable from Settings → Devices & Services without editing YAML. Holdings themselves stay in the repository layer (Section 2) — config entries are for *engine configuration*, not portfolio data, matching your original data/calculation separation. |
| Hot reload | Implement `async_unload_entry` + rely on HA's standard `entry.add_update_listener(async_reload_entry)` pattern, so changing options (provider, interval, thresholds) reloads the coordinator without a full HA restart. Holdings-file changes are picked up by a `watchdog`-style file watcher (or simply on the coordinator's own poll cycle if you'd rather avoid a dependency) that invalidates the repository cache. |
| Entity naming & device info | Every entity attaches to a single `DeviceInfo` per portfolio (`identifiers={(DOMAIN, portfolio_id)}`), so multiple portfolios show as distinct devices in the HA UI, each with its own set of sensors — this is what makes multi-portfolio (Section 6) show up cleanly rather than as one undifferentiated entity soup. Unique IDs follow `{portfolio_id}_{metric}` (e.g. `retirement_portfolio_value`), entity IDs derive from friendly names as HA does natively — don't hand-roll `entity_id`. |
| `engine.py` HA-independent | Unchanged from v2: the engine package (now `engine/` — see Section 5) has zero `homeassistant.*` imports and is pip-installable/testable standalone. The coordinator is the only place HA-specific code touches engine output. |

---

## 2. Repository Layer

The coordinator no longer reads YAML directly. It asks a `PortfolioRepository` for data and doesn't know or care where that data physically lives.

```python
# custom_components/portfolio_engine/repositories/base.py
from abc import ABC, abstractmethod
from ..models import Portfolio, Transaction

class PortfolioRepository(ABC):
    @abstractmethod
    async def async_get_portfolios(self) -> list[Portfolio]:
        """Return all portfolios with their current holdings/positions."""

    @abstractmethod
    async def async_get_transactions(self, portfolio_id: str) -> list[Transaction]:
        """Return transaction history for a portfolio, if the repository supports it."""

    @property
    def supports_transactions(self) -> bool:
        return False

    @property
    @abstractmethod
    def name(self) -> str:
        ...
```

Implementations:

| Repository | Backing store | Notes |
|---|---|---|
| `YamlRepository` | `/config/investments/*.yaml` | v1/v2 default. Read-only from the engine's perspective; edits happen via file or the Settings dashboard writing back to YAML. |
| `JsonRepository` | Local JSON (or SQLite via a thin JSON-shaped wrapper) | Same schema as YAML, useful once holdings volume or transaction history makes YAML unwieldy. |
| `BrokerRepository` | A broker API (Interactive Brokers, DEGIRO, etc.) | Holdings become **read-only from HA's side** — the broker is the source of truth, this repository just syncs. Naturally supports `supports_transactions = True` since brokers expose trade history. |
| `CloudRepository` | Google Sheets / a hosted DB | For people who want to edit holdings from a phone spreadsheet rather than YAML. |

```python
# custom_components/portfolio_engine/repositories/yaml_repository.py
import yaml
from pathlib import Path
from .base import PortfolioRepository
from ..models import Portfolio, Holding

class YamlRepository(PortfolioRepository):
    name = "yaml"

    def __init__(self, base_path: Path):
        self._base_path = base_path

    async def async_get_portfolios(self) -> list[Portfolio]:
        portfolios = []
        for portfolio_dir in sorted(self._base_path.glob("*/")):
            data = yaml.safe_load((portfolio_dir / "holdings.yaml").read_text())
            holdings = [Holding(**h) for h in data.get("holdings", [])]
            portfolios.append(Portfolio(
                id=portfolio_dir.name,
                name=data.get("name", portfolio_dir.name.title()),
                holdings=holdings,
            ))
        return portfolios

    async def async_get_transactions(self, portfolio_id: str) -> list:
        return []  # plain YAML holdings have no transaction history by default
```

The engine (and coordinator) call `repository.async_get_portfolios()` and never see a file path or an API client. Switching from YAML to Google Sheets is: write `CloudRepository`, change one config-entry option, done.

---

## 3. Currency Service

Split out from the engine, mirroring `PriceProvider`:

```python
# custom_components/portfolio_engine/providers/currency_base.py
from abc import ABC, abstractmethod

class CurrencyProvider(ABC):
    @abstractmethod
    async def async_get_rates(self, base: str, targets: list[str]) -> dict[str, float]:
        """Return {currency: rate_to_base}."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...
```

```
Price Provider  ──┐
                   ├──▶  Portfolio Engine
Currency Provider ─┘
```

`YahooFinanceCurrencyProvider` can piggyback on the same batched quote endpoint (`EURUSD=X` etc. are just symbols to Yahoo), but it's a **separate interface implementation**, not a method on `YahooFinanceProvider` — so a future setup could use Yahoo for prices and, say, the ECB's free rates API for FX, without the two being coupled. The coordinator fetches both and passes them into `PortfolioEngine` as independent inputs, exactly matching the diagram you specified.

---

## 4. Event-Driven Engine

Rather than one big `_async_update_data()` recomputing everything on every tick, the engine publishes and reacts to internal events on a lightweight in-process bus (no new dependency needed — `homeassistant.helpers.dispatcher` works fine for this, or a plain `asyncio`-friendly pub/sub if you want the engine package to stay fully HA-independent, dispatched by the coordinator at the boundary).

```python
# engine/events.py  (HA-independent)
from dataclasses import dataclass
from enum import Enum, auto

class EventType(Enum):
    PRICE_UPDATED = auto()
    HOLDING_CHANGED = auto()
    SETTINGS_CHANGED = auto()
    DIVIDEND_UPDATED = auto()
    TRANSACTION_ADDED = auto()

@dataclass
class EngineEvent:
    type: EventType
    payload: dict

class EventBus:
    def __init__(self):
        self._subscribers: dict[EventType, list] = {}

    def subscribe(self, event_type: EventType, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: EngineEvent):
        for handler in self._subscribers.get(event.type, []):
            await handler(event)
```

Practical effect for scale:

- A single price tick for `AAPL` fires `PRICE_UPDATED(symbol=AAPL)` → only the `PerformanceCalculator` and the one affected `HoldingResult` recompute; `AllocationCalculator` doesn't re-run unless the price move actually shifts allocation past a rounding threshold you define.
- Editing `holdings.yaml` fires `HOLDING_CHANGED` → full recalculation, since the shape of the portfolio itself changed.
- Editing `settings.yaml` (base currency, thresholds) fires `SETTINGS_CHANGED` → recompute summaries only, not prices.
- A new dividend datapoint fires `DIVIDEND_UPDATED` → only `DividendCalculator` runs.

This is genuinely more efficient at "hundreds of assets, frequent price ticks" scale than v2's "recompute everything every coordinator tick," at the cost of more moving parts — worth it once you're past a few dozen holdings; for a small personal portfolio, full recompute every 15 minutes (v2) is honestly still fine, so treat this as the upgrade path once you feel the coordinator tick getting heavy, not a day-one requirement.

---

## 5. Plugin / Calculator Architecture

```
engine/
├── __init__.py
├── events.py
├── models.py
├── portfolio_engine.py      # orchestrator only — no calculation logic itself
└── calculators/
    ├── base.py               # Calculator ABC
    ├── allocation.py         # AllocationCalculator
    ├── dividend.py           # DividendCalculator
    ├── performance.py        # PerformanceCalculator (CAGR, rolling returns)
    ├── goal.py                # GoalCalculator (progress, projection)
    ├── analytics.py           # AnalyticsCalculator (volatility, best/worst)
    └── risk.py                # RiskCalculator (Sharpe, max drawdown — future)
```

```python
# engine/calculators/base.py
from abc import ABC, abstractmethod
from ..events import EventType

class Calculator(ABC):
    #: which event types trigger this calculator
    triggers: tuple[EventType, ...] = ()

    @abstractmethod
    def calculate(self, portfolio_state: dict) -> dict:
        """Pure function: portfolio_state in, this calculator's contribution to results out."""
```

```python
# engine/portfolio_engine.py
class PortfolioEngine:
    def __init__(self, calculators: list[Calculator]):
        self._calculators = calculators

    def run(self, portfolio_state: dict, triggered_by: EventType | None = None) -> dict:
        results = {}
        for calc in self._calculators:
            if triggered_by is None or triggered_by in calc.triggers:
                results[calc.__class__.__name__] = calc.calculate(portfolio_state)
        return results
```

Adding a new metric (Sharpe ratio, say) is: write `RiskCalculator`, register it in the list passed to `PortfolioEngine`, done — `portfolio_engine.py` itself never changes. This directly satisfies "keeps each component small, makes future features easier to add," and each calculator is independently unit-testable with a fixed `portfolio_state` fixture.

---

## 6. Multi-Portfolio Support

Domain model gains a `Portfolio`/`Account` distinction from day one, plus a `GlobalPortfolio` aggregation:

```
GlobalPortfolio
├── Portfolio "Retirement"     (Account: broker_x)
├── Portfolio "Broker A"       (Account: broker_a)
├── Portfolio "Broker B"       (Account: broker_b)
├── Portfolio "Crypto"         (Account: exchange_y)
└── Portfolio "Paper"          (Account: none — simulated, excluded from real totals)
```

- Each `Portfolio` gets its own repository instance and its own `DeviceInfo` (Section 1) — so "Retirement" and "Broker A" can even use *different* repositories (one YAML, one `BrokerRepository`) simultaneously.
- `GlobalPortfolio` is not a separate data source — it's a calculator (`AggregationCalculator`) that sums results across all non-`Paper`-flagged portfolios. Watchlists stay per-portfolio or global, your choice, since they carry no value contribution.
- Dashboards get one additional top-level view — **"All Portfolios"** — plus the existing per-metric views (Overview, Portfolio, Holdings, ...) gain a portfolio selector (`input_select.active_portfolio`) at the top, defaulting to Global.
- Entity IDs become `sensor.retirement_portfolio_value`, `sensor.broker_a_portfolio_value`, `sensor.global_portfolio_value`, etc. — the `{portfolio_id}_{metric}` unique-ID convention from Section 1 makes this fall out naturally rather than requiring a redesign.

Because this is designed in from the start, going from 1 portfolio to 5 later is a config-entry addition (one more `Portfolio` block in a repository, or one more config entry if you want fully independent repositories per portfolio) — not a schema migration.

---

## 7. Domain Model

```python
# engine/models.py — HA-independent dataclasses, the shared vocabulary for the whole project
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Quote:
    symbol: str
    price: float
    currency: str
    change_pct: float
    as_of: datetime
    # ... (as in v2, Section 3.2)

@dataclass
class Holding:
    """Pure config — what a user entered. Maps directly to holdings.yaml."""
    symbol: str
    shares: float
    avg_price: float
    currency: str
    type: str
    account: str | None = None
    sector: str | None = None
    region: str | None = None

@dataclass
class Position:
    """A Holding + live market data — the calculated view, engine output only."""
    holding: Holding
    quote: Quote
    market_value: float
    market_value_base: float
    cost_basis: float
    unrealized_gain: float
    gain_pct: float

@dataclass
class Transaction:
    """One buy/sell/dividend/deposit event — the basis for realized gains and history."""
    id: str
    portfolio_id: str
    symbol: str | None          # None for cash deposits/withdrawals
    type: str                    # buy | sell | dividend | deposit | withdrawal | fee
    date: datetime
    shares: float | None
    price: float | None
    amount: float                # signed, in transaction currency
    currency: str
    notes: str | None = None

@dataclass
class Dividend:
    symbol: str
    ex_date: datetime
    pay_date: datetime | None
    amount_per_share: float
    currency: str

@dataclass
class Account:
    id: str
    name: str
    broker: str | None = None

@dataclass
class Portfolio:
    id: str
    name: str
    holdings: list[Holding] = field(default_factory=list)
    accounts: list[Account] = field(default_factory=list)
    is_paper: bool = False

@dataclass
class Goal:
    id: str
    portfolio_id: str | None     # None = applies to Global
    target_value: float
    target_date: datetime | None
    monthly_contribution: float | None = None

@dataclass
class Benchmark:
    symbol: str                  # e.g. a S&P 500 ETF/index used for comparison
    label: str
```

This is the "strong foundation" you asked for: `Transaction` is what unlocks realized gains and tax-lot reporting later; `Position` cleanly separates "what you own" (`Holding`) from "what it's currently worth" (engine-only, never persisted as config); `Benchmark` gives the future Analytics benchmark-comparison feature a first-class type to compare `Portfolio` performance against, rather than a hardcoded symbol string somewhere in a template.

---

## 8. Historical Data & Snapshots

Home Assistant's Recorder is good for entity state history but is the wrong tool for authoritative financial history (it purges, it's not designed for point-in-time portfolio reconstruction, and you don't want investment records at the mercy of `purge_keep_days`). Two additions:

1. **Transaction log** — persisted via `homeassistant.helpers.storage.Store` (HA's standard JSON-backed storage helper, atomic writes, survives restarts) at `.storage/portfolio_engine.transactions`, populated either manually (a `portfolio_engine.add_transaction` service you call from an automation or the UI) or automatically when a `BrokerRepository` syncs new trades.
2. **Daily snapshots** — a small scheduled job (part of the coordinator, or a separate lightweight coordinator on a `daily` interval) writes `{date, portfolio_id, total_value, total_cost, holdings_snapshot}` to `.storage/portfolio_engine.snapshots`. This is what actually enables:
   - Historical allocation ("what was my allocation 3 months ago") — Recorder statistics don't capture *composition*, only scalar sensor values.
   - **Time-weighted return (TWR)**: needs snapshots bracketing each cash flow, which is exactly what the snapshot store + transaction log together provide.
   - **Money-weighted return (MWR/IRR)**: computed purely from the transaction log's cash flows — no HA state needed at all, a good candidate for `PerformanceCalculator` to compute on demand rather than store.
   - **Benchmark comparison**: replay the same contribution schedule against `Benchmark.symbol`'s historical prices (pulled from the price provider's historical-data method, if it has one) and diff against actual TWR.

Keep this optional and lazy — `Store` files only get written to if you actually call the transaction-logging service or enable snapshotting in options, so a user who just wants live prices and doesn't care about tax reporting pays no cost for this layer existing.

---

## 9. Diagnostics & Observability

- **Diagnostic entities** (category `diagnostic`, so they don't clutter the main dashboards): `sensor.portfolio_engine_last_update`, `sensor.portfolio_engine_provider_status` (ok/degraded/down per provider), `sensor.portfolio_engine_refresh_duration`, `sensor.portfolio_engine_api_quota_remaining` (where the provider exposes it).
- **`diagnostics.py`** implementing HA's standard `async_get_config_entry_diagnostics` — this is what makes "Download Diagnostics" work from Settings → Devices & Services, giving you a redacted dump (API keys stripped) for bug reports, for free, using HA's existing UI.
- **Structured logging**: use `_LOGGER = logging.getLogger(__name__)` per module (standard HA pattern) rather than print/generic logging, so users can turn on debug logging for just `custom_components.portfolio_engine.providers.yahoo_finance` via `logger:` config when a specific provider misbehaves.
- **Health checks**: the coordinator should distinguish "provider returned an error" (mark entities `unavailable`, keep last-known values in state attributes, retry with backoff) from "provider returned stale/zero data for a symbol" (surface via the `provider_status` diagnostic sensor and the existing "Missing Price Data" automation from v1, rather than silently showing €0 holdings).
- **Graceful degradation**: if the price provider is down but the currency provider is up (or vice versa), the engine should still recompute whatever it can from last-known values rather than failing the whole update — this falls naturally out of the event-driven design in Section 4, since a failed `PRICE_UPDATED` for one symbol doesn't block calculators that don't depend on it.

---

## 10. Provider Roadmap

The `PriceProvider`/`CurrencyProvider` interfaces from Section 3/v2 already anticipate this — brokers are just providers that also happen to implement `PortfolioRepository` (Section 2) for holdings sync. No new abstraction needed, just:

| Category | Examples | Interface(s) implemented |
|---|---|---|
| Market data | Yahoo Finance, Finnhub, Twelve Data, Alpha Vantage, Polygon | `PriceProvider` (+ `CurrencyProvider` where they offer FX) |
| Broker/account sync | Interactive Brokers, DEGIRO | `PortfolioRepository` (holdings + transactions), optionally also `PriceProvider` if you want live prices sourced from the same connection |
| Manual/offline | CSV import | `PriceProvider` (static/delayed quotes) and/or `PortfolioRepository` (bulk transaction import) |

The engine and calculators never branch on "which provider is this" — they only ever call the interface methods, so this table can grow indefinitely without touching `engine/`.

---

## 11. Revised Folder Structure

```
custom_components/portfolio_engine/
├── __init__.py
├── manifest.json
├── config_flow.py
├── const.py
├── coordinator.py
├── diagnostics.py
├── repositories/
│   ├── base.py
│   ├── yaml_repository.py
│   ├── json_repository.py
│   ├── broker_repository.py
│   └── cloud_repository.py
├── providers/
│   ├── price_base.py
│   ├── currency_base.py
│   ├── yahoo_finance.py
│   ├── finnhub.py
│   └── csv_import.py
├── engine/                          # HA-independent, pip-installable/testable standalone
│   ├── events.py
│   ├── models.py
│   ├── portfolio_engine.py
│   └── calculators/
│       ├── base.py
│       ├── allocation.py
│       ├── dividend.py
│       ├── performance.py
│       ├── goal.py
│       ├── analytics.py
│       ├── risk.py
│       └── aggregation.py           # GlobalPortfolio rollup
├── sensor.py
├── diagnostics_sensors.py
└── services.yaml                     # portfolio_engine.add_transaction, .sync_now, etc.

/config/investments/
├── retirement/
│   ├── holdings.yaml
│   └── settings.yaml
├── broker_a/
│   └── holdings.yaml
├── crypto/
│   └── holdings.yaml
├── watchlist.yaml                    # global, or per-portfolio if preferred
├── markets.yaml
└── benchmarks.yaml                   # new: symbol + label pairs for comparison

/config/dashboards/investments/
├── all_portfolios.yaml               # new: Global aggregation view
├── overview.yaml
├── portfolio.yaml
├── holdings.yaml
├── allocation.yaml
├── markets.yaml
├── watchlist.yaml
├── dividends.yaml
├── goals.yaml
├── analytics.yaml
└── settings.yaml
```

---

## 12. Suggested Build Milestones

Given the scope now spans repositories, an event bus, seven calculators, multi-portfolio, transaction history, and diagnostics, I'd sequence delivery rather than attempt it in one pass:

1. **Foundation**: `engine/models.py`, `PortfolioRepository`/`YamlRepository`, `PriceProvider`/`YahooFinanceProvider`, `PortfolioEngine` with just `AllocationCalculator` + a basic summary calculator. Single portfolio. Full recompute per tick (skip the event bus for now).
2. **HA wiring**: `coordinator.py`, `config_flow.py` + `OptionsFlow`, `sensor.py` with the dedicated + attribute entities, `diagnostics.py`. Get this genuinely running in your HA instance before adding more.
3. **Currency service**: split `CurrencyProvider` out, verify multi-currency portfolios compute correctly.
4. **Remaining calculators**: `DividendCalculator`, `PerformanceCalculator`, `GoalCalculator`, `AnalyticsCalculator` — one at a time, each with its own dashboard view wired up as it lands.
5. **Multi-portfolio**: extend repository/config-entry model, add `AggregationCalculator` and the Global dashboard.
6. **Event-driven refactor**: introduce `EventBus`, migrate calculators to declare `triggers`, only worth doing once you're feeling coordinator-tick cost at your real portfolio size.
7. **Historical layer**: `Store`-backed transactions + snapshots, then `RiskCalculator` (Sharpe, drawdown, TWR/MWR) once there's real history to compute over.
8. **Broker/CSV repositories**: only once the core is stable — these are the highest-effort, most account-specific pieces, best done last.

I can start writing real, working code for Milestone 1 — `engine/models.py`, `repositories/base.py` + `yaml_repository.py`, `providers/price_base.py` + `yahoo_finance.py`, and a minimal `portfolio_engine.py` with one calculator — whenever you're ready to move from spec to implementation.
