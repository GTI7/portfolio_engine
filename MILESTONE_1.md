# Milestone 1: Foundation

**Status:** Complete, validated, ready to build on.

## What's included

- `engine/models.py` — the trimmed Milestone-1 domain model: `Quote`, `Holding` (with validation), `Position`, `Portfolio`, and the three calculators' result types. `Transaction`, `Dividend`, `Goal`, `Account`, `Benchmark` are **not** in this milestone — they're added when the milestone that needs them lands (Dividends, Goals, historical layer respectively).
- `engine/calculators/` — `PortfolioCalculator`, `AllocationCalculator`, `PerformanceCalculator` (day-change only; weekly/monthly/YTD stubbed at 0.0, see ADR-0003). No other calculators exist yet, per ADR-0004.
- `engine/portfolio_engine.py` — orchestrator. Builds `Position`s from `Holding`s + `Quote`s, then runs every registered calculator against them. Zero Home Assistant imports anywhere in `engine/`.
- `repositories/base.py` + `repositories/yaml_repository.py` — `PortfolioRepository` interface and its first implementation, reading `/investments/<portfolio_id>/holdings.yaml`. Pure I/O + validation; no calculation (ADR-0001).
- `providers/price_base.py` + `providers/yahoo_finance.py` — `PriceProvider` interface and Yahoo Finance implementation. Batches all symbols into one HTTP call. The HTTP fetch function is injected (not hardcoded to `aiohttp`) so the provider is testable without a network dependency and swappable for HA's shared client session later without changing the class.
- `docs/adr/` — five ADRs documenting the decisions made so far (repository pattern, provider/repository separation, Store-over-Recorder for later, minimal calculator set, deferred event-driven processing) plus a template for future ones.
- `tests/` — 20 tests, all passing, covering model validation, repository loading (including error cases: missing directory, missing file, invalid holding), provider batching behavior, each calculator in isolation, and one end-to-end engine run.

## Explicitly NOT in this milestone

Per the "solid foundation over every feature" principle: no currency conversion (single-currency portfolios are fully correct; mixed-currency will be inaccurate until Milestone 3 — this is documented inline in `portfolio_calculator.py` and `portfolio_engine.py`, not silently wrong), no multi-portfolio aggregation, no event-driven recalculation, no HA wiring yet (`custom_components/`, coordinator, config flow, sensors — Milestone 2), no dividends/goals/risk calculators, no transaction history or snapshots.

## How to validate it yourself

```bash
cd portfolio_engine
pip install -r requirements.txt -r requirements-test.txt
python -m pytest tests/ -v
```

Expect `20 passed`.

To see it work against real (non-network) data, run this from the `portfolio_engine/` directory:

```python
import asyncio
from pathlib import Path
from engine.calculators.allocation_calculator import AllocationCalculator
from engine.calculators.performance_calculator import PerformanceCalculator
from engine.calculators.portfolio_calculator import PortfolioCalculator
from engine.models import Quote
from engine.portfolio_engine import PortfolioEngine
from repositories.yaml_repository import YamlRepository

async def main():
    repo = YamlRepository(Path("sample_data"))
    portfolios = await repo.async_get_portfolios()
    portfolio = portfolios[0]

    # Fake quotes standing in for a real provider call — see
    # tests/test_yahoo_finance_provider.py for the real thing.
    quotes = {
        "AAPL": Quote(symbol="AAPL", price=195.32, currency="USD", change_pct=1.25),
        "MSFT": Quote(symbol="MSFT", price=421.10, currency="USD", change_pct=-0.42),
        "BTC-USD": Quote(symbol="BTC-USD", price=61000.0, currency="USD", change_pct=3.1),
    }

    engine = PortfolioEngine({
        "summary": PortfolioCalculator(),
        "allocation": AllocationCalculator(group_by="type"),
        "performance": PerformanceCalculator(),
    })
    result = engine.run(portfolio, quotes)
    print(result["summary"])
    print(result["allocation"])
    print(result["performance"])

asyncio.run(main())
```

## Migration notes

Nothing to migrate yet — this is the first code milestone, there is no prior YAML-packages implementation to retire. If you did already build any of the v1/v2 `packages/investment/*.yaml` template-sensor approach in your live HA instance, it can keep running unmodified in parallel; it doesn't share entity IDs or files with this engine. Retire it once Milestone 2 wires this engine's sensors into HA and you've confirmed they show correct data.

## Validation checklist (per-milestone requirement)

- [x] `pytest tests/` passes (20/20)
- [x] Every public class has a docstring explaining its single responsibility
- [x] No `homeassistant.*` import anywhere under `engine/`
- [x] No calculation logic in `repositories/` or `providers/` (grep confirms no `market_value`/`gain`/`roi` computation outside `engine/`)
- [x] Every deferred feature (currency conversion, extra calculators, event-driven processing) is documented at the point it's deferred, not silently missing
- [x] ADRs written for the 5 architectural decisions this milestone's code embodies

## Next milestone

**Milestone 2 — HA wiring**: `custom_components/portfolio_engine/` with `config_flow.py` (+ `OptionsFlow`), `coordinator.py` (`DataUpdateCoordinator` calling this engine on a poll interval), `sensor.py` (dedicated entities for `PortfolioSummary` fields + attribute-list entities for positions/allocation), and `diagnostics.py`. This is the first point the code actually runs inside Home Assistant rather than as a standalone Python package.
