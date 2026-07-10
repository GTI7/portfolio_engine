"""Diagnostics download tests."""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from custom_components.portfolio_engine.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_snapshot_shape(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # investments_path is redacted
    assert diagnostics["entry"]["data"][CONF_INVESTMENTS_PATH] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_UPDATE_INTERVAL_MINUTES] == 15

    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["last_error"] is None
    assert diagnostics["coordinator"]["update_interval_seconds"] == 15 * 60

    assert diagnostics["portfolio"]["portfolio_id"] == "demo_portfolio"
    assert diagnostics["portfolio"]["base_currency"] == "USD"
    assert diagnostics["portfolio"]["positions_count"] == 1
    assert diagnostics["portfolio"]["symbols_missing_quotes"] == []

    assert diagnostics["summary"]["total_value"] == 2500.0
    assert diagnostics["summary"]["cash_balance"] == 1000.0

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
