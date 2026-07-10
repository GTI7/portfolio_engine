"""Portfolio Engine integration setup.

Milestone 2 scope: single config entry -> single coordinator -> sensor
platform. Milestone 9 adds one service, `portfolio_engine.import_transactions`
(see services.py) - registered once (shared across every config entry,
since it's a domain-level service, not per-entry) and deregistered when
the last entry unloads.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, PLATFORMS
from .coordinator import REPAIR_ISSUE_KEYS, PortfolioCoordinator
from .services import (
    SERVICE_EXPORT_PORTFOLIO_DATA,
    SERVICE_IMPORT_TRANSACTIONS,
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
        # Milestone 9/10: both services are domain-level, not per-entry -
        # only remove them once no configured portfolio remains to use them.
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_IMPORT_TRANSACTIONS)
            hass.services.async_remove(DOMAIN, SERVICE_EXPORT_PORTFOLIO_DATA)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
