"""Milestone 10 — portfolio_engine.export_portfolio_data service tests."""
import json
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
from custom_components.portfolio_engine.services import SERVICE_EXPORT_PORTFOLIO_DATA

TRANSACTIONS_YAML = """
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
    shares: 10
    price: 100.0
    amount: 1000.0
    currency: USD
"""


async def _setup(hass, investments_dir, with_transactions=True):
    investments_dir.write_portfolio(cash_balance=0.0 if with_transactions else 1000.0)
    if with_transactions:
        investments_dir.write_transactions(raw_yaml=TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_export_service_is_registered(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_EXPORT_PORTFOLIO_DATA)


async def test_export_writes_a_complete_backup_file(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    output_file = tmp_path / "backup.json"
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXPORT_PORTFOLIO_DATA,
        {"portfolio": "demo_portfolio", "output_path": str(output_file)},
        blocking=True,
        return_response=True,
    )

    assert response["portfolio"] == "demo_portfolio"
    assert response["holdings_count"] == 1
    assert response["transactions_count"] == 2
    assert response["snapshots_count"] == 1  # first-ever refresh created one

    assert output_file.exists()
    bundle = json.loads(output_file.read_text())
    assert bundle["portfolio_id"] == "demo_portfolio"
    assert bundle["base_currency"] == "USD"
    assert len(bundle["holdings"]) == 1
    assert bundle["holdings"][0]["symbol"] == "AAPL"
    assert len(bundle["transactions"]) == 2
    assert len(bundle["snapshots"]) == 1
    assert "exported_at" in bundle

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_export_creates_parent_directories(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    output_file = tmp_path / "backups" / "nested" / "backup.json"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXPORT_PORTFOLIO_DATA,
        {"portfolio": "demo_portfolio", "output_path": str(output_file)},
        blocking=True,
    )

    assert output_file.exists()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_export_includes_last_import_when_present(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    from custom_components.portfolio_engine.services import SERVICE_IMPORT_TRANSACTIONS

    entry = await _setup(hass, investments_dir, with_transactions=False)

    import_file = tmp_path / "export.csv"
    import_file.write_text(
        "id,type,date,amount,currency,symbol,shares,price\n"
        "d1,deposit,2026-01-01T00:00:00Z,500.0,USD,,,\n"
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_TRANSACTIONS,
        {"portfolio": "demo_portfolio", "provider": "generic_csv", "file_path": str(import_file)},
        blocking=True,
    )
    await hass.async_block_till_done()

    output_file = tmp_path / "backup.json"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXPORT_PORTFOLIO_DATA,
        {"portfolio": "demo_portfolio", "output_path": str(output_file)},
        blocking=True,
    )

    bundle = json.loads(output_file.read_text())
    assert bundle["last_import"] is not None
    assert bundle["last_import"]["provider_name"] == "generic_csv"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_export_unknown_portfolio_raises_service_validation_error(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    tmp_path: Path,
) -> None:
    entry = await _setup(hass, investments_dir)

    with pytest.raises(ServiceValidationError, match="No configured Portfolio Engine"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EXPORT_PORTFOLIO_DATA,
            {"portfolio": "nonexistent", "output_path": str(tmp_path / "backup.json")},
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_both_services_deregistered_after_last_entry_unloads(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    from custom_components.portfolio_engine.services import SERVICE_IMPORT_TRANSACTIONS

    entry = await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_IMPORT_TRANSACTIONS)
    assert hass.services.has_service(DOMAIN, SERVICE_EXPORT_PORTFOLIO_DATA)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, SERVICE_IMPORT_TRANSACTIONS)
    assert not hass.services.has_service(DOMAIN, SERVICE_EXPORT_PORTFOLIO_DATA)
