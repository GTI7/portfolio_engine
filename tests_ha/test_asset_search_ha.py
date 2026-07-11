"""Milestone 11 — search_assets service against the real HA harness:
registration/deregistration lifecycle, response shape, default limit,
and the "pure discovery, no side effects" guarantee, verified as an
actual file-content check rather than just a doc claim.
"""

from pathlib import Path

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from custom_components.portfolio_engine.services import SERVICE_SEARCH_ASSETS


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
    assert hass.services.has_service(DOMAIN, SERVICE_SEARCH_ASSETS)


async def test_service_deregistered_after_last_entry_unloads(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)
    assert hass.services.has_service(DOMAIN, SERVICE_SEARCH_ASSETS)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, SERVICE_SEARCH_ASSETS)


async def test_search_returns_matches_for_a_mocked_yahoo_response(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    mock_asset_search_provider,
) -> None:
    entry = await _setup(hass, investments_dir)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_ASSETS,
        {"query": "Vanguard FTSE All-World", "limit": 5},
        blocking=True,
        return_response=True,
    )

    assert response["query"] == "Vanguard FTSE All-World"
    assert response["count"] == 1
    assert response["results"][0]["symbol"] == "VWCE.DE"
    assert response["results"][0]["exchange"] == "XETRA"
    assert response["results"][0]["currency"] == "EUR"
    assert response["results"][0]["asset_type"] == "etf"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_missing_limit_defaults_to_ten(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    mock_asset_search_provider,
) -> None:
    entry = await _setup(hass, investments_dir)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_ASSETS,
        {"query": "Apple"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_asset_search_provider == [("Apple", 10)]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_service_does_not_require_a_matching_configured_portfolio(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    mock_asset_search_provider,
) -> None:
    """Unlike import_transactions/export_portfolio_data, search_assets is
    domain-wide and never resolves a portfolio - a query unrelated to any
    configured portfolio must still succeed, not raise
    ServiceValidationError the way an unknown `portfolio` id would for the
    other two services.
    """
    entry = await _setup(hass, investments_dir)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_ASSETS,
        {"query": "something totally unrelated to any configured portfolio"},
        blocking=True,
        return_response=True,
    )

    assert response["count"] == 1  # the mocked provider always returns its one fixed result

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_service_call_does_not_touch_any_portfolio_file(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    mock_asset_search_provider,
) -> None:
    entry = await _setup(hass, investments_dir)

    holdings_file = Path(investments_dir.path) / "demo_portfolio" / "holdings.yaml"
    before = holdings_file.read_text()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_ASSETS,
        {"query": "Apple"},
        blocking=True,
    )
    await hass.async_block_till_done()

    after = holdings_file.read_text()
    assert before == after  # untouched - pure discovery, no side effects

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
