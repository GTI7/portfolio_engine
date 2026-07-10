"""Milestone 4 — transaction_count and reconciliation entities against the
real HA harness. See MILESTONE_4_SPEC.md Section 10's HA-harness list.
"""
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

MATCHING_TRANSACTIONS_YAML = """
transactions:
  - id: "11111111-1111-1111-1111-111111111111"
    type: deposit
    date: "2025-12-31T00:00:00Z"
    amount: 1000.0
    currency: USD
  - id: "22222222-2222-2222-2222-222222222222"
    type: buy
    date: "2026-01-01T00:00:00Z"
    symbol: AAPL
    shares: 10
    price: 100.0
    amount: 1000.0
    currency: USD
"""

MISMATCHED_TRANSACTIONS_YAML = """
transactions:
  - id: "33333333-3333-3333-3333-333333333333"
    type: deposit
    date: "2025-12-31T00:00:00Z"
    amount: 1000.0
    currency: USD
  - id: "44444444-4444-4444-4444-444444444444"
    type: buy
    date: "2026-01-01T00:00:00Z"
    symbol: AAPL
    shares: 5
    price: 100.0
    amount: 500.0
    currency: USD
"""


def _write_transactions_yaml(investments_dir, raw: str) -> None:
    investments_dir.write_transactions(raw_yaml=raw)


async def test_new_entities_register_on_same_device_as_existing_six(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    # cash_balance=0.0 matches MATCHING_TRANSACTIONS_YAML: deposit 1000,
    # then buy spends 1000 -> reconstructed cash balance is 0.
    investments_dir.write_portfolio(cash_balance=0.0)
    _write_transactions_yaml(investments_dir, MATCHING_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    transaction_entity = registry.async_get("sensor.demo_portfolio_transaction_count")
    reconciliation_entity = registry.async_get("sensor.demo_portfolio_reconciliation")
    value_entity = registry.async_get("sensor.demo_portfolio_value")

    assert transaction_entity is not None
    assert reconciliation_entity is not None
    assert transaction_entity.device_id == value_entity.device_id
    assert reconciliation_entity.device_id == value_entity.device_id
    assert transaction_entity.unique_id.startswith(entry.entry_id)
    assert reconciliation_entity.unique_id.startswith(entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_matching_transactions_yield_ok_reconciliation(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=0.0)
    _write_transactions_yaml(investments_dir, MATCHING_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reconciliation_state = hass.states.get("sensor.demo_portfolio_reconciliation")
    assert reconciliation_state.state == "ok"
    assert reconciliation_state.attributes["discrepancies"] == []

    transaction_state = hass.states.get("sensor.demo_portfolio_transaction_count")
    assert transaction_state.state == "2"
    assert len(transaction_state.attributes["recent"]) == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_mismatched_transactions_yield_discrepancy(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    # holdings.yaml declares the default 10 shares @ 100 (see conftest's
    # investments_dir.write_portfolio default), but the log only shows a
    # 5-share buy - a real discrepancy.
    investments_dir.write_portfolio(cash_balance=0.0)
    _write_transactions_yaml(investments_dir, MISMATCHED_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reconciliation_state = hass.states.get("sensor.demo_portfolio_reconciliation")
    assert reconciliation_state.state == "discrepancy"
    assert len(reconciliation_state.attributes["discrepancies"]) >= 1

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_portfolio_without_transactions_yaml_is_no_data_not_a_setup_failure(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """A portfolio without transaction history is fully valid and common -
    this must not be a setup failure. MILESTONE_4_SPEC.md Section 10.
    """
    investments_dir.write_portfolio()  # no transactions.yaml written at all

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reconciliation_state = hass.states.get("sensor.demo_portfolio_reconciliation")
    assert reconciliation_state.state == "no_data"

    transaction_state = hass.states.get("sensor.demo_portfolio_transaction_count")
    assert transaction_state.state == "0"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_reconciliation_block(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=0.0)
    _write_transactions_yaml(investments_dir, MATCHING_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["reconciliation"]["status"] == "ok"
    assert diagnostics["reconciliation"]["discrepancy_count"] == 0
    assert diagnostics["reconciliation"]["transactions_considered"] == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
