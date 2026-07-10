"""Setup + entity/device registration tests — the core "does it actually
work inside Home Assistant" validation for Milestone 2.5.
"""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)

EXPECTED_ENTITIES = {
    "sensor.demo_portfolio_value": ("2500.0", "USD"),  # 1500 position + 1000 cash
    "sensor.demo_portfolio_total_invested": ("1000.0", "USD"),
    "sensor.demo_portfolio_total_profit": ("500.0", "USD"),
    "sensor.demo_portfolio_roi": ("50.0", "%"),
    "sensor.demo_portfolio_cash_balance": ("1000.0", "USD"),
    "sensor.demo_portfolio_positions": ("1", "positions"),
}


async def _setup_entry(hass: HomeAssistant, investments_dir) -> MockConfigEntry:
    investments_dir.write_portfolio()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INVESTMENTS_PATH: investments_dir.path,
            CONF_UPDATE_INTERVAL_MINUTES: 15,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_creates_all_six_entities_with_correct_values(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup_entry(hass, investments_dir)

    for entity_id, (expected_state, expected_unit) in EXPECTED_ENTITIES.items():
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        assert state.state == expected_state, f"{entity_id}: {state.state!r} != {expected_state!r}"
        assert state.attributes.get("unit_of_measurement") == expected_unit

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_have_stable_unique_ids(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup_entry(hass, investments_dir)
    registry = er.async_get(hass)

    for entity_id in EXPECTED_ENTITIES:
        entity_entry = registry.async_get(entity_id)
        assert entity_entry is not None
        # Per ADR-0006/0009's entity-stability policy: unique_id must be
        # derived from the config entry, not from anything that could shift
        # across restarts (like insertion order or symbol list contents).
        assert entity_entry.unique_id.startswith(entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_share_one_device_per_portfolio(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup_entry(hass, investments_dir)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    device_ids = set()
    for entity_id in EXPECTED_ENTITIES:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry.device_id is not None
        device_ids.add(entity_entry.device_id)

    assert len(device_ids) == 1, "all six entities should share exactly one device"

    device = device_registry.async_get(next(iter(device_ids)))
    assert device is not None
    assert device.name == "Demo Portfolio"
    assert (DOMAIN, "demo_portfolio") in device.identifiers

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_positions_entity_carries_full_holdings_table_as_attributes(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(
        holdings=[
            {
                "symbol": "AAPL",
                "shares": 10,
                "avg_price": 100.0,
                "currency": "USD",
                "type": "stock",
            },
            {
                "symbol": "MSFT",
                "shares": 5,
                "avg_price": 200.0,
                "currency": "USD",
                "type": "stock",
            },
        ]
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_positions")
    assert state.state == "2"
    positions = state.attributes["positions"]
    assert len(positions) == 2
    assert {p["holding"]["symbol"] for p in positions} == {"AAPL", "MSFT"}

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
