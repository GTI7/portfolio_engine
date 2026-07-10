"""Milestone 5 — money-weighted return entity against the real HA harness."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from custom_components.portfolio_engine.diagnostics import (
    async_get_config_entry_diagnostics,
)

# A deposit several years before "now" plus growth to the sample
# portfolio's terminal value (10 shares @ 150 = 1500 + 1000 cash = 2500)
# from a 2000 deposit is a real, computable positive return - safely far
# enough in the past that "as_of = real now" (the coordinator's default,
# no injected as_of in production) still has meaningful time spread
# regardless of exactly when this test runs.
OK_TRANSACTIONS_YAML = """
transactions:
  - id: "55555555-5555-5555-5555-555555555555"
    type: deposit
    date: "2020-01-01T00:00:00Z"
    amount: 2000.0
    currency: USD
"""


async def test_mwr_entity_registers_on_same_device(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)
    investments_dir.write_transactions(raw_yaml=OK_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    mwr_entity = registry.async_get("sensor.demo_portfolio_money_weighted_return")
    value_entity = registry.async_get("sensor.demo_portfolio_value")

    assert mwr_entity is not None
    assert mwr_entity.device_id == value_entity.device_id
    assert mwr_entity.unique_id.startswith(entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_mwr_computes_ok_with_real_deposit_history(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)
    investments_dir.write_transactions(raw_yaml=OK_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_money_weighted_return")
    assert state is not None
    assert state.state != "unknown"
    assert float(state.state) > 0  # a real gain over several years
    assert state.attributes["status"] == "ok"
    assert state.attributes["cash_flow_count"] == 2
    assert state.attributes["unit_of_measurement"] == "%"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_mwr_is_unknown_state_when_no_transactions(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """No transactions.yaml at all -> "no_data" -> HA state "unknown", and
    setup must still succeed - same principle as the reconciliation entity
    in Milestone 4.
    """
    investments_dir.write_portfolio()  # no transactions.yaml

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_money_weighted_return")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["status"] == "no_data"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_mwr_is_unknown_when_only_internal_transactions(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """A log with only BUY (no external flows) is "no_data" per ADR-0011,
    not a crash or a nonsensical rate.
    """
    investments_dir.write_portfolio(cash_balance=1000.0)
    internal_only_yaml = """
transactions:
  - id: "66666666-6666-6666-6666-666666666666"
    type: buy
    date: "2025-01-01T00:00:00Z"
    symbol: AAPL
    shares: 10
    price: 100.0
    amount: 1000.0
    currency: USD
"""
    investments_dir.write_transactions(raw_yaml=internal_only_yaml)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_money_weighted_return")
    assert state.state == "unknown"
    assert state.attributes["status"] == "no_data"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_mwr_block(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)
    investments_dir.write_transactions(raw_yaml=OK_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["mwr"]["status"] == "ok"
    assert diagnostics["mwr"]["rate_pct"] is not None
    assert diagnostics["mwr"]["cash_flow_count"] == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
