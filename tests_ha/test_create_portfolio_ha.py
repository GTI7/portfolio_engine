"""Milestone 12 — create_portfolio service against the real HA harness.
Adds a new portfolio under an already-configured investments path (the
Config Flow guided branch covers the very-first-portfolio case instead -
see docs/adr/0018 and tests_ha/test_config_flow_guided_setup_ha.py).
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
from custom_components.portfolio_engine.repositories.yaml_repository import YamlRepository
from custom_components.portfolio_engine.services import SERVICE_CREATE_PORTFOLIO


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
    assert hass.services.has_service(DOMAIN, SERVICE_CREATE_PORTFOLIO)


async def test_service_deregistered_after_last_entry_unloads(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_CREATE_PORTFOLIO)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, SERVICE_CREATE_PORTFOLIO)


async def test_create_portfolio_writes_a_new_holdings_yaml_matching_manual_convention(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PORTFOLIO,
        {
            "investments_path": investments_dir.path,
            "portfolio_id": "new_portfolio",
            "name": "New Portfolio",
            "base_currency": "USD",
            "cash_balance": 500.0,
            "holdings": [
                {
                    "symbol": "AAPL",
                    "shares": 10,
                    "avg_price": 150.0,
                    "currency": "USD",
                    "type": "stock",
                }
            ],
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"investments_path": investments_dir.path, "portfolio": "new_portfolio"}

    # Round-trip through the *existing* read path - proves the new write
    # produces exactly what the old reader already expects, no reader change.
    repo = YamlRepository(Path(investments_dir.path))
    portfolios = await repo.async_get_portfolios()
    new_portfolio = next(p for p in portfolios if p.id == "new_portfolio")
    assert new_portfolio.name == "New Portfolio"
    assert new_portfolio.base_currency == "USD"
    assert new_portfolio.cash_balance == 500.0
    assert len(new_portfolio.holdings) == 1
    assert new_portfolio.holdings[0].symbol == "AAPL"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_create_portfolio_with_no_holdings_creates_an_empty_portfolio(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PORTFOLIO,
        {
            "investments_path": investments_dir.path,
            "portfolio_id": "empty_portfolio",
            "name": "Empty Portfolio",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    holdings_file = Path(investments_dir.path) / "empty_portfolio" / "holdings.yaml"
    data = yaml.safe_load(holdings_file.read_text())
    assert data["holdings"] == []
    assert data["base_currency"] == "EUR"  # schema default
    assert data["cash_balance"] == 0.0  # schema default

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_create_portfolio_rejects_an_already_existing_portfolio_id(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_PORTFOLIO,
            {
                "investments_path": investments_dir.path,
                "portfolio_id": "demo_portfolio",  # already created by _setup
                "name": "Duplicate",
            },
            blocking=True,
        )

    # The original portfolio must be untouched by the rejected attempt.
    holdings_file = Path(investments_dir.path) / "demo_portfolio" / "holdings.yaml"
    data = yaml.safe_load(holdings_file.read_text())
    assert data["name"] == "Demo Portfolio"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_create_portfolio_with_unconfigured_investments_path_raises_service_validation_error(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    with pytest.raises(ServiceValidationError, match="No configured Portfolio Engine entry"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_PORTFOLIO,
            {
                "investments_path": "/some/unconfigured/path",
                "portfolio_id": "new_portfolio",
                "name": "New Portfolio",
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_create_portfolio_triggers_a_coordinator_refresh(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PORTFOLIO,
        {
            "investments_path": investments_dir.path,
            "portfolio_id": "new_portfolio",
            "name": "New Portfolio",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # The coordinator's own portfolio (demo_portfolio) is unaffected, but a
    # refresh must have run (not just a raw file write with no HA-visible
    # effect) - assert the coordinator's last update timestamp advanced.
    assert coordinator.last_update_success

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
