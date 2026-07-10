"""Multi-currency validation against the real HA harness (Milestone 3) —
confirms base-currency conversion actually reaches the real entities, not
just the engine layer in isolation.
"""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)


async def test_multi_currency_portfolio_converts_to_base_currency(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
    mock_currency_provider,
) -> None:
    # Base currency EUR; one EUR holding, one USD holding needing conversion.
    investments_dir.write_portfolio(
        base_currency="EUR",
        cash_balance=0.0,
        holdings=[
            {
                "symbol": "MC.PA",
                "shares": 1,
                "avg_price": 600.0,
                "currency": "EUR",
                "type": "stock",
            },
            {
                "symbol": "AAPL",
                "shares": 10,
                "avg_price": 100.0,
                "currency": "USD",
                "type": "stock",
            },
        ],
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # mock_price_provider returns price=150.0 for every symbol regardless of
    # currency (see conftest.py) - so both positions are 150 * shares in
    # their own currency, and mock_currency_provider converts USD at 0.92.
    # MC.PA (EUR, already base): 1 * 150.0 = 150.0
    # AAPL (USD -> EUR at 0.92): 10 * 150.0 * 0.92 = 1380.0
    expected_total = 150.0 + (10 * 150.0 * 0.92)

    value_state = hass.states.get("sensor.demo_portfolio_value")
    assert value_state is not None
    assert float(value_state.state) == round(expected_total, 2)
    assert value_state.attributes.get("unit_of_measurement") == "EUR"

    positions_state = hass.states.get("sensor.demo_portfolio_positions")
    positions_by_symbol = {
        p["holding"]["symbol"]: p for p in positions_state.attributes["positions"]
    }
    assert positions_by_symbol["MC.PA"]["fx_rate"] == 1.0
    assert positions_by_symbol["AAPL"]["fx_rate"] == 0.92
    assert positions_state.attributes["fx_rates_missing"] == []

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_missing_fx_rate_surfaces_in_positions_attributes_not_a_crash(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    investments_dir,
    mock_price_provider,
) -> None:
    """Without mock_currency_provider, the real YahooFinanceCurrencyProvider
    would try a real network call - which we still don't want in this test
    suite (see mock_price_provider's own docstring on why). Instead this
    confirms the *fallback* path: patch the currency provider to return no
    rates at all, and confirm setup still succeeds with fx_rates_missing
    populated rather than the coordinator failing outright.
    """
    from unittest.mock import patch

    investments_dir.write_portfolio(
        base_currency="EUR",
        cash_balance=0.0,
        holdings=[
            {
                "symbol": "AAPL",
                "shares": 10,
                "avg_price": 100.0,
                "currency": "USD",
                "type": "stock",
            },
        ],
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)

    async def _no_rates(self, base, targets):
        return {base: 1.0}  # simulates the provider having no rate for USD

    with patch(
        "custom_components.portfolio_engine.providers.yahoo_finance_currency."
        "YahooFinanceCurrencyProvider.async_get_rates",
        new=_no_rates,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    positions_state = hass.states.get("sensor.demo_portfolio_positions")
    assert positions_state.attributes["fx_rates_missing"] == ["USD"]
    # setup still succeeded with a best-effort 1.0 fallback rather than
    # failing the whole entry over one missing rate
    assert hass.states.get("sensor.demo_portfolio_value").state != "unavailable"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
