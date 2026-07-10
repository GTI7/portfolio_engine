"""Fetch-and-compute logic, deliberately free of `homeassistant.*` imports.

This is the "thin integration" principle applied concretely: the actual
work a coordinator tick does (fetch portfolio config, fetch quotes, fetch
FX rates, run the engine, collect a snapshot) lives here as a plain async
function, fully unit-testable with pytest and fake repository/provider
implementations. `coordinator.py`'s `DataUpdateCoordinator` subclass is
then just a few lines of HA glue calling this function - see
docs/adr/0009-thin-coordinator-testable-update-logic.md.
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

from .engine.portfolio_engine import PortfolioEngine
from .engine.snapshot_policy import build_snapshot, should_create_snapshot
from .providers.currency_base import CurrencyProvider
from .providers.price_base import PriceProvider
from .repositories.base import PortfolioRepository
from .repositories.snapshot_base import SnapshotRepository


class PortfolioDataUnavailable(Exception):
    """Raised when there's nothing to compute from (no portfolios configured,
    or the configured portfolio has no holdings). Distinct from a provider/
    network failure so the coordinator (and, later, a Repair) can tell the
    two apart.
    """


async def async_fetch_portfolio_data(
    repository: PortfolioRepository,
    price_provider: PriceProvider,
    currency_provider: CurrencyProvider,
    snapshot_repository: SnapshotRepository,
    engine: PortfolioEngine,
) -> dict[str, Any]:
    """One full coordinator-tick's worth of work.

    Milestone 2 scope (unchanged by Milestone 3's currency support): single
    portfolio (the first one the repository returns). Multi-portfolio
    iteration is deferred - see the architecture doc's Section 6 and
    MILESTONE_2_PLAN.md; this function's shape doesn't need to change to
    support it later, just its caller.

    FX rates are only fetched for currencies that actually appear among the
    portfolio's holdings and differ from its base currency - a
    single-currency portfolio never calls the currency provider at all
    (see CurrencyProvider.async_get_rates's contract for why that's safe:
    a currency converting to itself is always rate 1.0, no lookup needed).

    Milestone 6: `portfolio.snapshots` is populated from a *separate*
    SnapshotRepository (not `repository` above) and attached here, per
    ADR-0012 - PortfolioRepository has no reason to know SnapshotRepository
    exists. After the engine runs (using whatever snapshots already
    existed), this function applies the collection policy
    (`should_create_snapshot`, "once per calendar date") and persists a new
    snapshot if warranted - a successful call to this function IS "a
    successful coordinator refresh" for policy purposes (MILESTONE_6 Phase
    3), so no separate signal is needed. The newly-created snapshot (if
    any) intentionally is NOT retroactively added to `portfolio.snapshots`
    for this run's TwrCalculator - it was created using this run's own
    computed value, so including it would be redundant with the synthetic
    "current value at as_of" boundary TwrCalculator already adds; it
    becomes a real historical boundary starting next run.

    Milestone 8: a SnapshotRepository failure (read or write) degrades
    gracefully rather than failing the whole refresh - `snapshots` falls
    back to an empty list (or whatever was already loaded, for a write
    failure) and `result["snapshot_repository_error"]` carries the error
    message, so prices/positions/every other metric still update normally.
    The coordinator surfaces this as a Repair issue rather than the
    integration going `unavailable` over a storage hiccup unrelated to
    market data.
    """
    portfolios = await repository.async_get_portfolios()
    if not portfolios:
        raise PortfolioDataUnavailable(
            "No portfolios found. Check the configured investments path."
        )

    portfolio = portfolios[0]
    symbols = sorted({holding.symbol for holding in portfolio.holdings})
    quotes = await price_provider.async_get_quotes(symbols)

    foreign_currencies = sorted(
        {holding.currency for holding in portfolio.holdings} - {portfolio.base_currency}
    )
    fx_rates = (
        await currency_provider.async_get_rates(portfolio.base_currency, foreign_currencies)
        if foreign_currencies
        else {}
    )
    fx_rates_missing = sorted(set(foreign_currencies) - set(fx_rates.keys()))

    existing_snapshots: list[Any] = []
    snapshot_repository_error: str | None = None
    try:
        existing_snapshots = await snapshot_repository.async_get_snapshots(portfolio.id)
    except Exception as err:  # noqa: BLE001 - any storage backend failure (Store I/O error,
        # corrupted data, etc.) should degrade gracefully, not take down prices/positions/
        # every other metric with it - Milestone 8's "production readiness" goal. The
        # coordinator surfaces this as a Repair issue (see coordinator.py's
        # _sync_repair_issues) rather than the whole refresh failing.
        snapshot_repository_error = str(err)
    portfolio = dataclasses.replace(portfolio, snapshots=existing_snapshots)

    result = engine.run(portfolio, quotes, fx_rates)
    result["portfolio_id"] = portfolio.id
    result["portfolio_name"] = portfolio.name
    result["base_currency"] = portfolio.base_currency
    result["symbols_requested"] = len(symbols)
    result["symbols_missing_quotes"] = sorted(set(symbols) - set(quotes.keys()))
    result["fx_rates"] = fx_rates
    result["fx_rates_missing"] = fx_rates_missing
    # Milestone 8: the full transaction list, purely for diagnostics.py's
    # transaction-statistics block (count by type, date range) - no
    # calculator or entity reads this key, so exposing it here changes no
    # existing behavior. TransactionCalculator's own `recent` (capped at
    # 10) remains the entity-facing view; this is the untrimmed source.
    result["portfolio_transactions"] = portfolio.transactions

    now = datetime.now(UTC)
    snapshot_created = False
    if snapshot_repository_error is None and should_create_snapshot(existing_snapshots, now):
        try:
            new_snapshot = build_snapshot(portfolio, result["summary"], result["positions"], now)
            await snapshot_repository.async_append_snapshot(new_snapshot)
            snapshot_created = True
        except Exception as err:  # noqa: BLE001 - same graceful-degradation reasoning as above
            snapshot_repository_error = str(err)

    all_snapshots = [*existing_snapshots, new_snapshot] if snapshot_created else existing_snapshots
    result["snapshot_created"] = snapshot_created
    result["snapshots"] = all_snapshots
    result["snapshot_repository_error"] = snapshot_repository_error

    return result
