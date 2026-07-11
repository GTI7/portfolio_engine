"""Portfolio Engine integration setup.

Milestone 2 scope: single config entry -> single coordinator -> sensor
platform. Milestone 9 adds `portfolio_engine.import_transactions`,
Milestone 10 adds `portfolio_engine.export_portfolio_data`, Milestone 11
adds `portfolio_engine.search_assets`, Milestone 12 adds
`portfolio_engine.apply_import` and `portfolio_engine.create_portfolio`
(see services.py) - all five are domain-level services (shared across
every config entry, not per-entry), registered once and deregistered
when the last entry unloads.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, PLATFORMS
from .coordinator import REPAIR_ISSUE_KEYS, PortfolioCoordinator
from .services import (
    SERVICE_APPLY_IMPORT,
    SERVICE_CREATE_PORTFOLIO,
    SERVICE_EXPORT_PORTFOLIO_DATA,
    SERVICE_IMPORT_TRANSACTIONS,
    SERVICE_SEARCH_ASSETS,
    async_register_services,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Portfolio Engine from a config entry."""
    coordinator = PortfolioCoordinator(hass, entry)

    # First refresh happens during setup so a genuinely broken config
    # (bad path, unreachable provider) surfaces as a setup failure rather
    # than a silently-unavailable integration the user has to notice later.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    async_register_services(hass)

    # Hot reload on options change (e.g. update interval edited via
    # OptionsFlow) — standard HA pattern, no restart required.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Milestone 8: clean up any Repair issues this entry created - an
        # unloaded/removed entry shouldn't leave orphaned issues behind in
        # the Repairs UI for a portfolio that no longer exists.
        for key in REPAIR_ISSUE_KEYS:
            ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_{key}")
        # Milestone 9/10/11/12: all five services are domain-level, not
        # per-entry - only remove them once no configured portfolio remains
        # to use them. (Milestone 13 Phase 2 fix: apply_import/
        # create_portfolio, added in Milestone 12, were never added to this
        # cleanup list - a real bug, not just a theoretical gap:
        # tests_ha/test_apply_import_ha.py and test_create_portfolio_ha.py
        # already had their own test_service_deregistered_after_last_entry_unloads
        # tests asserting exactly this, written alongside each service in
        # Milestone 12 - they simply couldn't run locally on this Windows
        # dev environment (tests_ha/'s known ProactorEventLoop limitation),
        # so this went unnoticed until this review, rather than being an
        # intentionally-deferred decision.)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_IMPORT_TRANSACTIONS)
            hass.services.async_remove(DOMAIN, SERVICE_EXPORT_PORTFOLIO_DATA)
            hass.services.async_remove(DOMAIN, SERVICE_SEARCH_ASSETS)
            hass.services.async_remove(DOMAIN, SERVICE_APPLY_IMPORT)
            hass.services.async_remove(DOMAIN, SERVICE_CREATE_PORTFOLIO)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
