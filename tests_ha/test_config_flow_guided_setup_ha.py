"""Milestone 12 — Config Flow's guided-setup branch: today's
investments_path_not_found dead end gains an opt-in path to creating the
folder and a first portfolio inline. See docs/adr/0018.
"""
import yaml
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)


async def test_declining_guided_setup_still_shows_existing_error_unchanged(
    hass: HomeAssistant, enable_custom_integrations: None, tmp_path
) -> None:
    nonexistent_path = str(tmp_path / "does_not_exist")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_INVESTMENTS_PATH: nonexistent_path,
            CONF_UPDATE_INTERVAL_MINUTES: 15,
            # create_new_portfolio omitted - defaults to False
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "investments_path_not_found"


async def test_guided_setup_creates_folder_and_first_portfolio(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    tmp_path,
    mock_asset_search_provider,
) -> None:
    new_root = tmp_path / "brand_new_investments"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_INVESTMENTS_PATH: str(new_root),
            CONF_UPDATE_INTERVAL_MINUTES: 15,
            "create_new_portfolio": True,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "guided_portfolio"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "portfolio_id": "new_portfolio",
            "name": "New Portfolio",
            "base_currency": "USD",
            "cash_balance": 500.0,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "guided_search"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"query": "Vanguard FTSE All-World"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "guided_pick"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selection": "0", "shares": 5, "avg_price": 100.0},
    )
    # Loops back to search for another holding.
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "guided_search"

    # Blank query finishes the loop and creates the entry.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"query": ""}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INVESTMENTS_PATH] == str(new_root)
    assert result["data"][CONF_UPDATE_INTERVAL_MINUTES] == 15
    # The transient checkbox never leaks into stored config entry data.
    assert "create_new_portfolio" not in result["data"]

    holdings_file = new_root / "new_portfolio" / "holdings.yaml"
    data = yaml.safe_load(holdings_file.read_text())
    assert data["name"] == "New Portfolio"
    assert data["base_currency"] == "USD"
    assert data["cash_balance"] == 500.0
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["symbol"] == "VWCE.DE"
    assert data["holdings"][0]["shares"] == 5

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_guided_setup_with_no_search_matches_shows_form_error(
    hass: HomeAssistant, enable_custom_integrations: None, tmp_path
) -> None:
    from unittest.mock import patch

    new_root = tmp_path / "brand_new_investments"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_INVESTMENTS_PATH: str(new_root),
            CONF_UPDATE_INTERVAL_MINUTES: 15,
            "create_new_portfolio": True,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"portfolio_id": "new_portfolio", "name": "New Portfolio"},
    )

    async def _empty_search(self, query, limit=10):
        return []

    with patch(
        "custom_components.portfolio_engine.providers.yahoo_finance_asset_search."
        "YahooFinanceAssetSearchProvider.async_search",
        new=_empty_search,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"query": "something with no matches"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "guided_search"
    assert result["errors"]["base"] == "no_matches"


async def test_second_portfolio_under_same_path_ignores_create_new_portfolio_flag(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """Once the path already exists, create_new_portfolio has no effect -
    the guided branch only ever fires for a not-yet-existing path. Adding a
    2nd+ portfolio under an existing path uses the create_portfolio service
    instead (tests_ha/test_create_portfolio_ha.py), never this flow.
    """
    investments_dir.write_portfolio()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_INVESTMENTS_PATH: investments_dir.path,
            CONF_UPDATE_INTERVAL_MINUTES: 15,
            "create_new_portfolio": True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
