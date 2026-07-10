"""Config flow for Portfolio Engine.

Milestone 2 scope: one setup step (investments path + initial update
interval) and one options step (update interval only, editable after setup
without reconstructing the entry). Provider/repository *choice* is out of
scope — Milestone 2 hardcodes Yahoo Finance + YamlRepository, matching
"expose the engine, don't expand it" — see MILESTONE_2_PLAN.md.

Milestone 10: two configuration-UX fixes.
1. Unique ID is now the investments path itself, not a fixed domain-wide
   constant - the original design blocked a *second config entry ever
   existing*, full stop, even though services.py's coordinator lookup
   (_find_coordinator_for_portfolio, Milestone 9) already iterates over
   every registered entry and has supported multiple portfolios since it
   was written. Now genuinely distinct setups (different investments
   paths, each pointing at its own portfolio folder) are allowed; the
   exact same path twice is still rejected, same as before.
2. A reconfigure flow (async_step_reconfigure) lets a user change the
   investments path in place, instead of deleting and re-adding the whole
   config entry (which would also mean rebuilding Store-backed snapshot/
   import history under a new entry_id) just to fix a typo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DEFAULT_INVESTMENTS_PATH,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    MIN_UPDATE_INTERVAL_MINUTES,
)


def _investments_path_exists(hass: HomeAssistant, relative_path: str) -> bool:
    return Path(hass.config.path(relative_path)).exists()


class PortfolioEngineConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            investments_path = user_input[CONF_INVESTMENTS_PATH]

            if not _investments_path_exists(self.hass, investments_path):
                errors["base"] = "investments_path_not_found"
            else:
                # Milestone 10: unique per investments_path, not per domain
                # - allows more than one config entry to exist (each
                # tracking a different investments folder / portfolio),
                # while still rejecting a duplicate setup of the exact same
                # path.
                await self.async_set_unique_id(investments_path)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Portfolio Engine ({investments_path})",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_INVESTMENTS_PATH, default=DEFAULT_INVESTMENTS_PATH
                ): str,
                vol.Required(
                    CONF_UPDATE_INTERVAL_MINUTES, default=DEFAULT_UPDATE_INTERVAL_MINUTES
                ): vol.All(int, vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES)),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Milestone 10 — edit an existing entry's investments path or
        update interval in place, instead of remove-and-re-add. Keeps the
        same entry_id, so Store-backed snapshot/last-import history
        (both keyed by entry_id) survives the change untouched.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            investments_path = user_input[CONF_INVESTMENTS_PATH]

            if not _investments_path_exists(self.hass, investments_path):
                errors["base"] = "investments_path_not_found"
            else:
                # Re-check uniqueness against the *new* path, but allow
                # keeping the same path this entry already has (that's not
                # a duplicate, it's a no-op edit to the other field) -
                # _abort_if_unique_id_configured already excludes the
                # entry currently being reconfigured from that check.
                await self.async_set_unique_id(investments_path)
                self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    entry, title=f"Portfolio Engine ({investments_path})", data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_INVESTMENTS_PATH,
                    default=entry.data.get(CONF_INVESTMENTS_PATH, DEFAULT_INVESTMENTS_PATH),
                ): str,
                vol.Required(
                    CONF_UPDATE_INTERVAL_MINUTES,
                    default=entry.data.get(
                        CONF_UPDATE_INTERVAL_MINUTES, DEFAULT_UPDATE_INTERVAL_MINUTES
                    ),
                ): vol.All(int, vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES)),
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PortfolioEngineOptionsFlow:
        return PortfolioEngineOptionsFlow(config_entry)


class PortfolioEngineOptionsFlow(config_entries.OptionsFlow):
    """Post-setup tuning: update interval only, per Milestone 2 scope."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL_MINUTES,
            self.config_entry.data.get(
                CONF_UPDATE_INTERVAL_MINUTES, DEFAULT_UPDATE_INTERVAL_MINUTES
            ),
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_UPDATE_INTERVAL_MINUTES, default=current): vol.All(
                    int, vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
