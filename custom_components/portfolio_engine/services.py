"""portfolio_engine.import_transactions, portfolio_engine.export_portfolio_data,
and portfolio_engine.search_assets services.

import_transactions reads a broker export file, runs it through the
requested BrokerImportProvider, builds an ImportReport (duplicate-checked
against the portfolio's current transaction log), persists it as the
portfolio's "last import" (for the sensor.<portfolio>_last_import entity
and diagnostics), and returns a JSON-safe summary as the service's
response data. Deliberately does NOT write to transactions.yaml - see
importers/report.py's ImportReport docstring and
docs/user/BROKER_IMPORT.md for why that's a manual step the user takes
after reviewing the report, not something this service does automatically.

export_portfolio_data (Milestone 10) is the opposite direction and the
opposite write-safety shape: it produces a single JSON backup file (all of
a portfolio's holdings, transactions, snapshot history, and last import
report) at a path the user explicitly names in the service call. This is
an *explicit* write, to a *new* file of the user's own choosing - not an
automatic modification of transactions.yaml or any file this integration
already owns, so it doesn't conflict with the "no automatic writes"
principle the import service is built around.

search_assets (Milestone 11) is domain-wide, not portfolio-scoped - unlike
the two services above, it has nothing to do with any configured
portfolio's data, so it does NOT use _find_coordinator_for_portfolio. It
never reads or writes any portfolio file at all - see
providers/asset_search_base.py and docs/adr/0014 for the two-call Yahoo
search+enrich design this delegates to.
"""

from __future__ import annotations

import functools
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import PortfolioCoordinator
from .importers.base import BrokerImportProvider
from .importers.generic_csv_importer import GenericCsvImporter
from .importers.ibkr_flex_query_importer import IbkrFlexQueryImporter
from .importers.report import build_import_report
from .providers.asset_search_base import AssetSearchResult
from .providers.yahoo_finance_asset_search import YahooFinanceAssetSearchProvider
from .yahoo_auth import YahooCrumbFetcher

_LOGGER = logging.getLogger(__name__)

SERVICE_IMPORT_TRANSACTIONS = "import_transactions"
SERVICE_EXPORT_PORTFOLIO_DATA = "export_portfolio_data"
SERVICE_SEARCH_ASSETS = "search_assets"

#: The two importers this milestone ships, per MILESTONE_9's explicit
#: "start with only two importers" scope - adding a third later is a
#: one-line addition here, the same shape as adding a new calculator to
#: coordinator.py's registry.
_PROVIDERS: dict[str, type[BrokerImportProvider]] = {
    "generic_csv": GenericCsvImporter,
    "ibkr_flex_query": IbkrFlexQueryImporter,
}

IMPORT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("portfolio"): cv.string,
        vol.Required("provider"): vol.In(_PROVIDERS.keys()),
        vol.Required("file_path"): cv.string,
    }
)

EXPORT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("portfolio"): cv.string,
        vol.Required("output_path"): cv.string,
    }
)

SEARCH_ASSETS_SCHEMA = vol.Schema(
    {
        vol.Required("query"): cv.string,
        vol.Optional("limit", default=10): vol.All(int, vol.Range(min=1, max=25)),
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    if not hass.services.has_service(DOMAIN, SERVICE_IMPORT_TRANSACTIONS):

        async def _handle_import_transactions(call: ServiceCall) -> ServiceResponse:
            return await _async_import_transactions(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_IMPORT_TRANSACTIONS,
            _handle_import_transactions,
            schema=IMPORT_SERVICE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_EXPORT_PORTFOLIO_DATA):

        async def _handle_export_portfolio_data(call: ServiceCall) -> ServiceResponse:
            return await _async_export_portfolio_data(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_EXPORT_PORTFOLIO_DATA,
            _handle_export_portfolio_data,
            schema=EXPORT_SERVICE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SEARCH_ASSETS):

        async def _handle_search_assets(call: ServiceCall) -> ServiceResponse:
            return await _async_search_assets(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEARCH_ASSETS,
            _handle_search_assets,
            schema=SEARCH_ASSETS_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )


def _read_file(path: Path) -> str:
    # Milestone 10 QoL fix: "utf-8-sig" transparently strips a leading
    # UTF-8 byte-order-mark if present, falling back to plain UTF-8
    # decoding when there isn't one - Excel (a very common source of
    # broker CSV exports) writes a BOM by default, and without this a
    # BOM'd file's header row parses as '\ufeffid' instead of 'id',
    # silently failing GenericCsvImporter's required-column check.
    return path.read_text(encoding="utf-8-sig")


async def _async_import_transactions(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    portfolio_id = call.data["portfolio"]
    provider_name = call.data["provider"]
    file_path = call.data["file_path"]

    coordinator = _find_coordinator_for_portfolio(hass, portfolio_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured Portfolio Engine portfolio found with id {portfolio_id!r}"
        )

    full_path = Path(hass.config.path(file_path))
    if not full_path.exists():
        raise ServiceValidationError(f"File not found: {file_path}")

    try:
        file_content = await hass.async_add_executor_job(_read_file, full_path)
    except OSError as err:
        raise ServiceValidationError(f"Could not read {file_path}: {err}") from err

    importer_cls = _PROVIDERS[provider_name]
    importer = importer_cls()
    parse_result = importer.parse(file_content, portfolio_id)

    existing_transactions = coordinator.data.get("portfolio_transactions", [])
    report = build_import_report(
        importer.name,
        portfolio_id,
        parse_result,
        existing_transactions,
        as_of=datetime.now(UTC),
    )

    await coordinator.import_report_store.async_save_report(report)
    await coordinator.async_request_refresh()

    _LOGGER.info(
        "Portfolio Engine import for %s via %s: %d read, %d imported, %d duplicates, %d rejected",
        portfolio_id,
        provider_name,
        report.transactions_read,
        report.imported_count,
        report.duplicate_count,
        report.rejected_count,
    )

    return {
        "provider": report.provider_name,
        "portfolio": report.portfolio_id,
        "transactions_read": report.transactions_read,
        "imported": report.imported_count,
        "duplicates": report.duplicate_count,
        "rejected": report.rejected_count,
        "warnings": report.warnings,
        "rejected_details": [
            {"source_line": r.source_line, "error": r.error} for r in report.rejected
        ],
    }


def _find_coordinator_for_portfolio(
    hass: HomeAssistant, portfolio_id: str
) -> PortfolioCoordinator | None:
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if coordinator.data and coordinator.data.get("portfolio_id") == portfolio_id:
            return coordinator
    return None


async def _async_export_portfolio_data(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    portfolio_id = call.data["portfolio"]
    output_path = call.data["output_path"]

    coordinator = _find_coordinator_for_portfolio(hass, portfolio_id)
    if coordinator is None:
        raise ServiceValidationError(
            f"No configured Portfolio Engine portfolio found with id {portfolio_id!r}"
        )

    # Read straight from the repository/snapshot store, not coordinator.data -
    # a backup should reflect the full holdings/transaction/snapshot record,
    # not just whatever this run's engine output happened to carry.
    portfolios = await coordinator.repository.async_get_portfolios()
    portfolio = next((p for p in portfolios if p.id == portfolio_id), None)
    if portfolio is None:
        raise ServiceValidationError(
            f"Portfolio {portfolio_id!r} is configured but no longer found in the "
            "repository - check your investments path."
        )

    snapshots = await coordinator.snapshot_repository.async_get_snapshots(portfolio_id)
    last_import = await coordinator.import_report_store.async_get_last_report(portfolio_id)

    exported_at = datetime.now(UTC).isoformat()
    bundle = {
        "exported_at": exported_at,
        "portfolio_id": portfolio.id,
        "portfolio_name": portfolio.name,
        "base_currency": portfolio.base_currency,
        "cash_balance": portfolio.cash_balance,
        "holdings": [_holding_to_dict(h) for h in portfolio.holdings],
        "transactions": [_transaction_to_dict(t) for t in portfolio.transactions],
        "snapshots": [s.to_dict() for s in snapshots],
        "last_import": last_import.to_dict() if last_import else None,
    }

    full_output_path = Path(hass.config.path(output_path))
    try:
        await hass.async_add_executor_job(_write_export_file, full_output_path, bundle)
    except OSError as err:
        raise ServiceValidationError(f"Could not write {output_path}: {err}") from err

    _LOGGER.info(
        "Portfolio Engine export for %s: %d holdings, %d transactions, %d snapshots -> %s",
        portfolio_id,
        len(portfolio.holdings),
        len(portfolio.transactions),
        len(snapshots),
        output_path,
    )

    return {
        "portfolio": portfolio.id,
        "output_path": output_path,
        "exported_at": exported_at,
        "holdings_count": len(portfolio.holdings),
        "transactions_count": len(portfolio.transactions),
        "snapshots_count": len(snapshots),
    }


def _write_export_file(path: Path, bundle: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")


def _holding_to_dict(holding: Any) -> dict[str, Any]:
    return {
        "symbol": holding.symbol,
        "shares": holding.shares,
        "avg_price": holding.avg_price,
        "currency": holding.currency,
        "type": holding.type,
        "account": holding.account,
    }


def _transaction_to_dict(txn: Any) -> dict[str, Any]:
    """A small, local serialization helper - deliberately not shared with
    importers/report.py's own private `_transaction_to_dict` (which exists
    for a different purpose, Store-backed ImportReport persistence). The
    two features evolve independently and the mapping itself is trivial
    (six fields, no business logic to drift on), so a shared abstraction
    here would be coupling for its own sake, not genuine reuse.
    """
    return {
        "id": txn.id,
        "type": txn.type.value,
        "date": txn.date.isoformat(),
        "currency": txn.currency,
        "amount": txn.amount,
        "symbol": txn.symbol,
        "shares": txn.shares,
        "price": txn.price,
        "notes": txn.notes,
    }


async def _plain_json_fetch(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    """Unauthenticated GET+JSON, for the search endpoint only. Per ADR-0014,
    Yahoo's public search endpoint (unlike the quote endpoint) needs no
    crumb - verified against the live API before this was written - so this
    deliberately does not go through YahooCrumbFetcher.
    """
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


def _asset_search_result_to_dict(result: AssetSearchResult) -> dict[str, Any]:
    return {
        "symbol": result.symbol,
        "name": result.name,
        "exchange": result.exchange,
        "currency": result.currency,
        "asset_type": result.asset_type,
    }


async def _async_search_assets(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    query = call.data["query"]
    limit = call.data["limit"]

    session = async_get_clientsession(hass)
    search_fetch = functools.partial(_plain_json_fetch, session)
    quote_fetch = YahooCrumbFetcher(session).fetch
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search(query, limit=limit)

    _LOGGER.info("Portfolio Engine asset search for %r: %d match(es)", query, len(results))

    return {
        "query": query,
        "count": len(results),
        "results": [_asset_search_result_to_dict(r) for r in results],
    }
