"""Recovery-from-failure tests: malformed YAML, provider errors, transient
network failures, and recovery once the underlying problem is fixed.
"""
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)


def _make_entry(investments_dir) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )


async def test_no_portfolios_configured_leaves_entry_not_ready(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    # investments_dir exists but is empty - no portfolio subdirectory at all
    entry = _make_entry(investments_dir)
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_malformed_yaml_leaves_entry_not_ready_not_crashed(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(raw_yaml="holdings: [this is: not, valid: yaml: at all")
    entry = _make_entry(investments_dir)
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The important property: HA is told the entry isn't ready and schedules
    # a retry (standard recoverable-failure handling), rather than an
    # unhandled exception propagating out of setup and destabilizing HA.
    assert result is False
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_invalid_holding_data_leaves_entry_not_ready_not_crashed(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    # negative shares - Holding.__post_init__ raises ValueError
    investments_dir.write_portfolio(
        holdings=[
            {
                "symbol": "AAPL",
                "shares": -5,
                "avg_price": 100.0,
                "currency": "USD",
                "type": "stock",
            }
        ]
    )
    entry = _make_entry(investments_dir)
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_provider_failure_marks_entities_unavailable_not_crashed(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """Set up successfully once, then simulate the price provider failing on
    a later refresh (e.g. a transient network error) - entities should
    become 'unavailable', not disappear or crash the coordinator.
    """
    investments_dir.write_portfolio()
    entry = _make_entry(investments_dir)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.demo_portfolio_value").state == "2500.0"

    coordinator = hass.data[DOMAIN][entry.entry_id]
    with patch(
        "custom_components.portfolio_engine.providers.yahoo_finance."
        "YahooFinanceProvider.async_get_quotes",
        side_effect=ConnectionError("simulated transient network failure"),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_value")
    assert state.state == "unavailable"
    assert coordinator.last_update_success is False
    assert "simulated transient network failure" in (coordinator.last_error or "")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_recovers_after_transient_failure_clears(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """The same scenario as above, but confirms recovery once the provider
    starts working again on a subsequent refresh - this is the actual
    'recovery', not just the failure half.
    """
    investments_dir.write_portfolio()
    entry = _make_entry(investments_dir)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    with patch(
        "custom_components.portfolio_engine.providers.yahoo_finance."
        "YahooFinanceProvider.async_get_quotes",
        side_effect=ConnectionError("simulated transient network failure"),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert hass.states.get("sensor.demo_portfolio_value").state == "unavailable"

    # mock_price_provider's patch on async_get_quotes is still active here
    # (the ConnectionError patch above was scoped to its own `with` block
    # and has already exited) - the next refresh should succeed again.
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_value")
    assert state.state == "2500.0"
    assert coordinator.last_update_success is True
    assert coordinator.last_error is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
