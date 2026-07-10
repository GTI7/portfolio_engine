"""Milestone 8 — entity polish regression guard: every entity must have an
icon set. Not a functional test (icons don't affect behavior), but exactly
the kind of thing that's easy to silently regress on the next entity added
without a check like this catching it.
"""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)

ALL_ENTITY_IDS = [
    "sensor.demo_portfolio_value",
    "sensor.demo_portfolio_total_invested",
    "sensor.demo_portfolio_total_profit",
    "sensor.demo_portfolio_roi",
    "sensor.demo_portfolio_cash_balance",
    "sensor.demo_portfolio_positions",
    "sensor.demo_portfolio_transaction_count",
    "sensor.demo_portfolio_reconciliation",
    "sensor.demo_portfolio_money_weighted_return",
    "sensor.demo_portfolio_time_weighted_return",
    "sensor.demo_portfolio_dividend_income",
    "sensor.demo_portfolio_drawdown",
    "sensor.demo_portfolio_volatility",
    "sensor.demo_portfolio_concentration",
    "sensor.demo_portfolio_last_import",
]


async def test_every_entity_has_an_icon(
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

    assert len(ALL_ENTITY_IDS) == 15  # the full public API surface, per docs/ENTITY_CONTRACTS.md

    for entity_id in ALL_ENTITY_IDS:
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        icon = state.attributes.get("icon")
        assert icon is not None, f"{entity_id} has no icon set"
        assert icon.startswith("mdi:"), f"{entity_id}'s icon {icon!r} is not an mdi icon"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_no_entity_uses_diagnostic_category(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """Confirms the deliberate decision documented in sensor.py's module
    docstring: every entity, including reconciliation, stays in the main
    entity list (entity_category unset) rather than being classified as
    EntityCategory.DIAGNOSTIC.
    """
    from homeassistant.helpers import entity_registry as er

    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    for entity_id in ALL_ENTITY_IDS:
        entity_entry = registry.async_get(entity_id)
        assert entity_entry.entity_category is None, (
            f"{entity_id} unexpectedly has entity_category={entity_entry.entity_category}"
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_no_entity_has_an_invalid_device_class_state_class_combination(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """Milestone 9 — regression test for a real bug caught via HA-harness
    log output: SensorDeviceClass.MONETARY only permits state_class None
    or "total", never "measurement". HA silently drops an invalid
    combination at runtime rather than raising, so this needs an explicit
    check - a passing test suite alone wouldn't have caught the original
    bug, since HA degrades gracefully instead of failing loudly.
    """
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in ALL_ENTITY_IDS:
        state = hass.states.get(entity_id)
        device_class = state.attributes.get("device_class")
        state_class = state.attributes.get("state_class")
        if device_class == "monetary":
            assert state_class in (None, "total"), (
                f"{entity_id}: device_class=monetary with state_class={state_class!r} "
                "is an invalid combination Home Assistant will silently reject"
            )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
