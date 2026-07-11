"""Milestone 12 — apply_import service against the real HA harness. Closes
the gap Milestone 9's import_transactions deliberately left open (report
only, never writes) - see docs/adr/0017.
"""
from pathlib import Path

import pytest
import yaml
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from custom_components.portfolio_engine.services import (
    SERVICE_APPLY_IMPORT,
    SERVICE_IMPORT_TRANSACTIONS,
)

FIRST_CSV_CONTENT = (
    "id,type,date,symbol,shares,price,amount,currency,notes\n"
    "d1,deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
    "b1,buy,2026-01-02T00:00:00Z,AAPL,5,100.0,500.0,USD,\n"
)
SECOND_CSV_CONTENT = (
    "id,type,date,symbol,shares,price,amount,currency,notes\n"
    "d2,deposit,2026-02-01T00:00:00Z,,,,250.0,USD,\n"
)


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


async def _import(hass, csv_content: str, tmp_path: Path, filename: str = "export.csv") -> None:
    export_file = tmp_path / filename
    export_file.write_text(csv_content)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {"portfolio": "demo_portfolio", "provider": "generic_csv", "file_path": str(export_file)},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_service_is_registered(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_APPLY_IMPORT)


async def test_service_deregistered_after_last_entry_unloads(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_APPLY_IMPORT)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, SERVICE_APPLY_IMPORT)


async def test_apply_import_with_no_pending_report_raises_service_validation_error(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    with pytest.raises(ServiceValidationError, match="No pending import report"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_APPLY_IMPORT,
            {"portfolio": "demo_portfolio"},
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_apply_import_writes_imported_rows_and_clears_the_report(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)
    await _import(hass, FIRST_CSV_CONTENT, tmp_path)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_APPLY_IMPORT,
        {"portfolio": "demo_portfolio"},
        blocking=True,
        return_response=True,
    )

    assert response == {"portfolio": "demo_portfolio", "applied_count": 2}

    transactions_file = Path(investments_dir.path) / "demo_portfolio" / "transactions.yaml"
    data = yaml.safe_load(transactions_file.read_text())
    assert {t["id"] for t in data["transactions"]} == {"d1", "b1"}

    # Report cleared - a second apply without a fresh import fails clearly
    # rather than double-appending.
    with pytest.raises(ServiceValidationError, match="No pending import report"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_APPLY_IMPORT,
            {"portfolio": "demo_portfolio"},
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_apply_import_triggers_a_coordinator_refresh(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)
    await _import(hass, FIRST_CSV_CONTENT, tmp_path)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    transactions_before = len(coordinator.data.get("portfolio_transactions", []))

    await hass.services.async_call(
        DOMAIN,
        SERVICE_APPLY_IMPORT,
        {"portfolio": "demo_portfolio"},
        blocking=True,
    )
    await hass.async_block_till_done()

    transactions_after = len(coordinator.data.get("portfolio_transactions", []))
    assert transactions_after == transactions_before + 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bak_file_holds_prior_content_after_a_second_apply_import(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)
    portfolio_dir = Path(investments_dir.path) / "demo_portfolio"

    await _import(hass, FIRST_CSV_CONTENT, tmp_path, "first.csv")
    await hass.services.async_call(
        DOMAIN, SERVICE_APPLY_IMPORT, {"portfolio": "demo_portfolio"}, blocking=True
    )
    await hass.async_block_till_done()
    first_content = (portfolio_dir / "transactions.yaml").read_text()

    await _import(hass, SECOND_CSV_CONTENT, tmp_path, "second.csv")
    await hass.services.async_call(
        DOMAIN, SERVICE_APPLY_IMPORT, {"portfolio": "demo_portfolio"}, blocking=True
    )
    await hass.async_block_till_done()

    bak_file = portfolio_dir / "transactions.yaml.bak"
    assert bak_file.exists()
    assert bak_file.read_text() == first_content

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unknown_portfolio_raises_service_validation_error(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    with pytest.raises(ServiceValidationError, match="No configured Portfolio Engine"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_APPLY_IMPORT,
            {"portfolio": "nonexistent_portfolio"},
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
