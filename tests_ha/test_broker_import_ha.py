"""Milestone 9 — broker import service and sensor.<portfolio>_last_import
entity against the real HA harness: service call, entity/diagnostics
reflection, error handling.
"""
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from custom_components.portfolio_engine.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.portfolio_engine.services import SERVICE_IMPORT_TRANSACTIONS

GENERIC_CSV_CONTENT = (
    "id,type,date,symbol,shares,price,amount,currency,notes\n"
    "d1,deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
    "b1,buy,2026-01-02T00:00:00Z,AAPL,5,100.0,500.0,USD,\n"
)

MATCHING_TRANSACTIONS_YAML = """
transactions:
  - id: "d1"
    type: deposit
    date: "2026-01-01T00:00:00Z"
    amount: 1000.0
    currency: USD
  - id: "b1"
    type: buy
    date: "2026-01-02T00:00:00Z"
    symbol: AAPL
    shares: 5
    price: 100.0
    amount: 500.0
    currency: USD
"""


async def _setup(hass, investments_dir):
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_service_is_registered(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_IMPORT_TRANSACTIONS)


async def test_import_service_call_returns_a_report(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    export_file = tmp_path / "export.csv"
    export_file.write_text(GENERIC_CSV_CONTENT)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {
            "portfolio": "demo_portfolio",
            "provider": "generic_csv",
            "file_path": str(export_file),
        },
        blocking=True,
        return_response=True,
    )

    assert response["transactions_read"] == 2
    assert response["imported"] == 2
    assert response["duplicates"] == 0
    assert response["rejected"] == 0

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_import_updates_last_import_entity(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    state_before = hass.states.get("sensor.demo_portfolio_last_import")
    assert state_before.state == "unknown"
    assert state_before.attributes["status"] == "never_imported"

    export_file = tmp_path / "export.csv"
    export_file.write_text(GENERIC_CSV_CONTENT)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {"portfolio": "demo_portfolio", "provider": "generic_csv", "file_path": str(export_file)},
        blocking=True,
    )
    await hass.async_block_till_done()

    state_after = hass.states.get("sensor.demo_portfolio_last_import")
    assert state_after.state == "2"
    assert state_after.attributes["status"] == "ok"
    assert state_after.attributes["provider"] == "generic_csv"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_import_persists_across_a_restart_simulation(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    export_file = tmp_path / "export.csv"
    export_file.write_text(GENERIC_CSV_CONTENT)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {"portfolio": "demo_portfolio", "provider": "generic_csv", "file_path": str(export_file)},
        blocking=True,
    )
    await hass.async_block_till_done()

    # "restart": full unload then setup again, same pattern as
    # tests_ha/test_snapshot_twr_ha.py's snapshot-persistence test
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.demo_portfolio_last_import")
    assert state.state == "2"  # the import survived the "restart"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reimport_is_detected_as_duplicates(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    """Realistic scenario: import, manually add the imported transactions
    to transactions.yaml (simulated here by writing them directly), then
    re-run the same import - everything should now show as duplicates.
    """
    entry = await _setup(hass, investments_dir)

    export_file = tmp_path / "export.csv"
    export_file.write_text(GENERIC_CSV_CONTENT)

    # first import
    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {"portfolio": "demo_portfolio", "provider": "generic_csv", "file_path": str(export_file)},
        blocking=True,
    )
    await hass.async_block_till_done()

    # simulate the user having copied the imported transactions into their
    # real log
    investments_dir.write_transactions(raw_yaml=MATCHING_TRANSACTIONS_YAML)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()  # pick up the newly-written transactions.yaml
    await hass.async_block_till_done()

    # re-import the same file
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {"portfolio": "demo_portfolio", "provider": "generic_csv", "file_path": str(export_file)},
        blocking=True,
        return_response=True,
    )

    assert response["imported"] == 0
    assert response["duplicates"] == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unknown_portfolio_raises_service_validation_error(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    export_file = tmp_path / "export.csv"
    export_file.write_text(GENERIC_CSV_CONTENT)

    with pytest.raises(ServiceValidationError, match="No configured Portfolio Engine"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IMPORT_TRANSACTIONS,
            {
                "portfolio": "nonexistent_portfolio",
                "provider": "generic_csv",
                "file_path": str(export_file),
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_missing_file_raises_service_validation_error(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    with pytest.raises(ServiceValidationError, match="File not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IMPORT_TRANSACTIONS,
            {
                "portfolio": "demo_portfolio",
                "provider": "generic_csv",
                "file_path": "/nonexistent/path/export.csv",
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_last_import_block(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    export_file = tmp_path / "export.csv"
    export_file.write_text(GENERIC_CSV_CONTENT)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {"portfolio": "demo_portfolio", "provider": "generic_csv", "file_path": str(export_file)},
        blocking=True,
    )
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["last_import"]["provider"] == "generic_csv"
    assert diagnostics["last_import"]["imported"] == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_service_deregistered_after_last_entry_unloads(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_IMPORT_TRANSACTIONS)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, SERVICE_IMPORT_TRANSACTIONS)
