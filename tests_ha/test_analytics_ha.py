"""Milestone 7 — dividend/drawdown/volatility/concentration entities
against the real HA harness. Per MILESTONE_7_DESIGN.md's testing plan:
registration/device grouping, unknown-state, ok computation, diagnostics -
same four-test shape every prior return-metric entity has used since
Milestone 5.
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

DIVIDEND_TRANSACTIONS_YAML = """
transactions:
  - id: "77777777-7777-7777-7777-777777777777"
    type: dividend
    date: "2026-06-01T00:00:00Z"
    symbol: AAPL
    amount: 25.0
    currency: USD
"""

NEW_ENTITY_IDS = {
    "sensor.demo_portfolio_dividend_income",
    "sensor.demo_portfolio_drawdown",
    "sensor.demo_portfolio_volatility",
    "sensor.demo_portfolio_concentration",
}


async def test_all_four_new_entities_register_on_same_device(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    value_entity = registry.async_get("sensor.demo_portfolio_value")

    for entity_id in NEW_ENTITY_IDS:
        entity_entry = registry.async_get(entity_id)
        assert entity_entry is not None, f"{entity_id} was not created"
        assert entity_entry.device_id == value_entity.device_id
        assert entity_entry.unique_id.startswith(entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_dividend_income_unknown_with_no_dividends(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_dividend_income")
    assert state.state == "unknown"
    assert state.attributes["status"] == "no_data"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_dividend_income_ok_with_dividend_transactions(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)
    investments_dir.write_transactions(raw_yaml=DIVIDEND_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_dividend_income")
    assert state.state != "unknown"
    assert float(state.state) == 25.0
    assert state.attributes["status"] == "ok"
    assert state.attributes["lifetime"] == 25.0
    assert state.attributes["unit_of_measurement"] == "USD"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_drawdown_unknown_with_no_snapshot_history(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """A brand-new portfolio has no prior Snapshot yet (today's just-
    created one doesn't count for a real reading) - same "unknown, not an
    error" convention as MWR/TWR on first-ever setup.
    """
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Drawdown is actually computable from a single snapshot (trivially
    # "at peak"), unlike MWR/TWR/Volatility, but "today's snapshot" is
    # created AFTER the engine run this refresh (see update_logic.py's
    # docstring), so this first-ever refresh still has zero snapshots in
    # portfolio.snapshots at calculation time.
    state = hass.states.get("sensor.demo_portfolio_drawdown")
    assert state.state == "unknown"
    assert state.attributes["status"] == "no_data"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_volatility_unknown_with_insufficient_snapshot_history(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_volatility")
    assert state.state == "unknown"
    assert state.attributes["status"] in ("no_data", "insufficient_data")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_concentration_ok_on_first_setup(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """Unlike the snapshot-dependent entities, concentration is purely
    derived from current positions - it's computable immediately, even on
    a brand-new portfolio's very first refresh.
    """
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_concentration")
    assert state.state != "unknown"
    assert state.attributes["status"] == "ok"
    assert state.attributes["largest_position"]["symbol"] == "AAPL"
    assert state.attributes["holding_count"] == 1

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_all_four_new_blocks(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)
    investments_dir.write_transactions(raw_yaml=DIVIDEND_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["dividends"]["status"] == "ok"
    assert diagnostics["dividends"]["lifetime"] == 25.0
    assert "drawdown" in diagnostics
    assert "volatility" in diagnostics
    assert diagnostics["concentration"]["status"] == "ok"
    assert diagnostics["concentration"]["holding_count"] == 1
    assert diagnostics["twr"]["annualized_pct"] is None  # no snapshot history yet

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
