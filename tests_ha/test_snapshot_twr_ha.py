"""Milestone 6 — snapshot collection (Store-backed) and the TWR entity
against the real HA harness. See MILESTONE_6 Phase 3/5's own test list.
"""
from datetime import UTC, datetime, timedelta

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
from custom_components.portfolio_engine.engine.models import Snapshot
from custom_components.portfolio_engine.store_snapshot_repository import (
    StoreSnapshotRepository,
)


async def test_first_refresh_creates_exactly_one_snapshot(
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

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["snapshots"]["count"] == 1
    assert diagnostics["snapshots"]["created_this_refresh"] is True
    assert diagnostics["snapshots"]["latest_timestamp"] is not None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_second_refresh_same_day_does_not_duplicate(
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

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()  # a second refresh, same calendar day
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["snapshots"]["count"] == 1  # still just one
    assert diagnostics["snapshots"]["created_this_refresh"] is False  # this refresh didn't add one

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_restart_does_not_duplicate_todays_snapshot(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """Simulates a Home Assistant restart: unload the entry (tearing down
    the coordinator and its StoreSnapshotRepository instance entirely),
    then set it up again (a fresh coordinator, fresh StoreSnapshotRepository
    instance, same entry_id -> same underlying Store data). The persisted
    snapshot from before "restart" must still be there, and no duplicate
    should be created for the same calendar day.
    """
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics_before = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics_before["snapshots"]["count"] == 1

    # "restart": full unload, then set up again - a brand new
    # PortfolioCoordinator and StoreSnapshotRepository object are
    # constructed, reading whatever was actually persisted to Store.
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics_after = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics_after["snapshots"]["count"] == 1  # no duplicate across "restart"
    assert diagnostics_after["snapshots"]["created_this_refresh"] is False

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_twr_entity_registers_on_same_device(
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
    twr_entity = registry.async_get("sensor.demo_portfolio_time_weighted_return")
    value_entity = registry.async_get("sensor.demo_portfolio_value")

    assert twr_entity is not None
    assert twr_entity.device_id == value_entity.device_id
    assert twr_entity.unique_id.startswith(entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_twr_is_unknown_on_first_ever_setup(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """A brand-new portfolio has no prior Snapshot to form a period against
    yet (today's just-created snapshot doesn't count - see update_logic.py's
    docstring) - TWR should be "unknown", not an error, and setup must
    still succeed.
    """
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_time_weighted_return")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["status"] in ("no_data", "insufficient_data")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_twr_computes_ok_with_a_prior_snapshot(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)

    # Pre-seed a snapshot from "yesterday" directly via the real
    # StoreSnapshotRepository, before the integration's own setup ever
    # runs - simulates a portfolio that's already been tracked for a while.
    repo = StoreSnapshotRepository(hass, entry.entry_id)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    await repo.async_append_snapshot(
        Snapshot(
            id="seed-1",
            portfolio_id="demo_portfolio",
            timestamp=yesterday,
            portfolio_value=2000.0,
            cash_balance=500.0,
            invested=1500.0,
            base_currency="USD",
        )
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_time_weighted_return")
    assert state is not None
    assert state.state != "unknown"
    assert state.attributes["status"] == "ok"
    assert state.attributes["periods_used"] == 1
    assert state.attributes["unit_of_measurement"] == "%"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_snapshots_and_twr_blocks(
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

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert "snapshots" in diagnostics
    assert diagnostics["snapshots"]["count"] == 1
    assert "twr" in diagnostics
    assert diagnostics["twr"]["status"] in ("no_data", "insufficient_data")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
