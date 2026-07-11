"""DataUpdateCoordinator for the Portfolio Engine integration.

Deliberately thin per ADR-0009 — all actual work happens in
`update_logic.async_fetch_portfolio_data()`. This class exists to satisfy
Home Assistant's polling/caching/error-propagation conventions
(`DataUpdateCoordinator` is the standard mechanism for exactly that) and to
wire together the concrete repository/provider/engine instances this
integration uses.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from .engine.calculators.allocation_calculator import AllocationCalculator
from .engine.calculators.base import Calculator
from .engine.calculators.dividend_calculator import DividendCalculator
from .engine.calculators.drawdown_calculator import DrawdownCalculator
from .engine.calculators.mwr_calculator import MwrCalculator
from .engine.calculators.performance_calculator import PerformanceCalculator
from .engine.calculators.portfolio_calculator import PortfolioCalculator
from .engine.calculators.position_analytics_calculator import PositionAnalyticsCalculator
from .engine.calculators.reconciliation_calculator import ReconciliationCalculator
from .engine.calculators.transaction_calculator import TransactionCalculator
from .engine.calculators.twr_calculator import TwrCalculator
from .engine.calculators.volatility_calculator import VolatilityCalculator
from .engine.portfolio_engine import PortfolioEngine
from .import_report_store import ImportReportStore
from .providers.currency_base import CurrencyProvider
from .providers.price_base import PriceProvider
from .providers.yahoo_finance import YahooFinanceProvider
from .providers.yahoo_finance_currency import YahooFinanceCurrencyProvider
from .repositories.yaml_repository import YamlRepository
from .store_snapshot_repository import StoreSnapshotRepository
from .update_logic import PortfolioDataUnavailable, async_fetch_portfolio_data
from .yahoo_auth import YahooCrumbFetcher

_LOGGER = logging.getLogger(__name__)

#: Every Repair issue key this integration can create - used by
#: __init__.py's async_unload_entry to clean up on unload/removal, so a
#: removed config entry doesn't leave orphaned issues in the Repairs UI.
REPAIR_ISSUE_KEYS = (
    "malformed_transaction_history",
    "reconciliation_discrepancy",
    "missing_fx_rates",
    "snapshot_repository_unavailable",
)


def _build_calculators() -> dict[str, Calculator]:
    # Eleven calculators as of Milestone 7 — the seven "platform" ones
    # (Milestones 1-6) plus four analytics calculators added in one pass,
    # each independently pluggable and testable, per MILESTONE_7_DESIGN.md.
    # No further calculators are planned without a design pass first — see
    # that document's "why no new ADR" section for the reasoning this
    # milestone stayed within the existing plugin architecture unchanged.
    #
    # Milestone 8: split out from _build_engine() (which just wraps this)
    # so the coordinator can also expose the registry for diagnostics
    # ("calculator versions" - see diagnostics.py's note on why that's a
    # registry snapshot, not literal per-calculator version numbers) -
    # this is a coordinator-level refactor only, no engine/ file touched,
    # no engine version bump needed.
    return {
        "summary": PortfolioCalculator(),
        "allocation": AllocationCalculator(group_by="type"),
        "performance": PerformanceCalculator(),
        "reconciliation": ReconciliationCalculator(),
        "transactions": TransactionCalculator(),
        "mwr": MwrCalculator(),
        "twr": TwrCalculator(),
        "dividends": DividendCalculator(),
        "drawdown": DrawdownCalculator(),
        "volatility": VolatilityCalculator(),
        "concentration": PositionAnalyticsCalculator(),
    }


class PortfolioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinates polling for one config entry's portfolio data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval_minutes = entry.options.get(
            CONF_UPDATE_INTERVAL_MINUTES,
            entry.data.get(CONF_UPDATE_INTERVAL_MINUTES, DEFAULT_UPDATE_INTERVAL_MINUTES),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
        )
        self.entry = entry

        investments_path = Path(hass.config.path(entry.data[CONF_INVESTMENTS_PATH]))
        # Milestone 12: exposed publicly (not just used to construct
        # self.repository) so services.py's apply_import/create_portfolio
        # can construct their own YamlPortfolioWriter against the same
        # base path, without PortfolioRepository itself gaining any write
        # capability - see docs/adr/0015.
        self.base_path = investments_path
        self.repository = YamlRepository(investments_path)

        session = async_get_clientsession(hass)

        # v1.0.1: query1.finance.yahoo.com/v7/finance/quote has required a
        # session cookie + crumb token since mid-2024; a bare request now
        # gets 401. YahooCrumbFetcher.fetch has the same FetchFn signature
        # the old plain closure did, so this is a same-shape substitution -
        # neither provider below changes.
        yahoo_fetch = YahooCrumbFetcher(session).fetch

        self.price_provider: PriceProvider = YahooFinanceProvider(fetch=yahoo_fetch)
        self.currency_provider: CurrencyProvider = YahooFinanceCurrencyProvider(
            fetch=yahoo_fetch
        )
        self.snapshot_repository = StoreSnapshotRepository(hass, entry.entry_id)
        self.import_report_store = ImportReportStore(hass, entry.entry_id)
        self.calculators = _build_calculators()
        self.engine = PortfolioEngine(self.calculators)

        # Diagnostics/observability fields (Milestone 2 scope: last-update
        # bookkeeping only; a dedicated diagnostic sensor entity and
        # per-provider health status are documented as Milestone 2b/2c
        # follow-ups in MILESTONE_2_PLAN.md, not implemented here).
        self.last_update_success_time: str | None = None
        self.last_error: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await async_fetch_portfolio_data(
                self.repository,
                self.price_provider,
                self.currency_provider,
                self.snapshot_repository,
                self.engine,
            )
        except PortfolioDataUnavailable as err:
            self.last_error = str(err)
            raise UpdateFailed(str(err)) from err
        except (ValueError, yaml.YAMLError) as err:
            # Milestone 8: malformed transaction/holdings data (a Transaction/
            # Holding/Snapshot failing its own __post_init__ validation, or a
            # YAML parse error) is a distinct, actionable case from a generic
            # failure - the user can fix their file, unlike a network outage.
            # Surfaced as both the standard UpdateFailed (unchanged retry/
            # unavailable behavior) AND a persistent Repair issue naming the
            # actual problem, so it doesn't just silently retry forever.
            self.last_error = str(err)
            self._create_issue(
                "malformed_transaction_history",
                translation_placeholders={"error": str(err)},
            )
            raise UpdateFailed(f"Invalid portfolio data: {err}") from err
        except Exception as err:  # noqa: BLE001 - any repository/provider
            # failure (bad YAML, network error, provider outage) is surfaced
            # to HA as UpdateFailed so the coordinator's own retry/backoff
            # and entity `unavailable` handling take over, rather than the
            # exception propagating raw and crashing the update loop.
            _LOGGER.exception("Unexpected error updating portfolio data")
            self.last_error = str(err)
            raise UpdateFailed(f"Unexpected error fetching portfolio data: {err}") from err

        self.last_error = None
        data["last_import_report"] = await self.import_report_store.async_get_last_report(
            data["portfolio_id"]
        )
        self._delete_issue("malformed_transaction_history")
        self._sync_repair_issues(data)
        return data

    def _issue_id(self, key: str) -> str:
        return f"{self.entry.entry_id}_{key}"

    def _create_issue(
        self, key: str, *, translation_placeholders: dict[str, str] | None = None
    ) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._issue_id(key),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=key,
            translation_placeholders=translation_placeholders,
        )

    def _delete_issue(self, key: str) -> None:
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(key))

    def _sync_repair_issues(self, data: dict[str, Any]) -> None:
        """Create or clear Repair issues based on this refresh's result -
        called only after a successful refresh (the malformed-data and
        generic-failure cases above handle their own issue directly, since
        `data` doesn't exist yet in those paths). Every condition here is
        re-evaluated every refresh, so a resolved problem clears itself on
        the next successful tick without any separate cleanup step.
        """
        reconciliation = data.get("reconciliation")
        if reconciliation is not None and reconciliation.status == "discrepancy":
            self._create_issue(
                "reconciliation_discrepancy",
                translation_placeholders={
                    "count": str(len(reconciliation.discrepancies)),
                },
            )
        else:
            self._delete_issue("reconciliation_discrepancy")

        fx_rates_missing = data.get("fx_rates_missing", [])
        if fx_rates_missing:
            self._create_issue(
                "missing_fx_rates",
                translation_placeholders={"currencies": ", ".join(fx_rates_missing)},
            )
        else:
            self._delete_issue("missing_fx_rates")

        snapshot_repository_error = data.get("snapshot_repository_error")
        if snapshot_repository_error:
            self._create_issue(
                "snapshot_repository_unavailable",
                translation_placeholders={"error": snapshot_repository_error},
            )
        else:
            self._delete_issue("snapshot_repository_unavailable")
