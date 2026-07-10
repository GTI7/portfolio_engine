"""Milestone 8 — diagnostics expansion tests: repository/provider identity,
calculator registry, environment/compatibility info, expanded snapshot and
transaction statistics, benchmarks reference.
"""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from custom_components.portfolio_engine.diagnostics import (
    async_get_config_entry_diagnostics,
)

TRANSACTIONS_YAML = """
transactions:
  - id: "11111111-1111-1111-1111-111111111111"
    type: deposit
    date: "2026-01-01T00:00:00Z"
    amount: 1000.0
    currency: USD
  - id: "22222222-2222-2222-2222-222222222222"
    type: buy
    date: "2026-02-01T00:00:00Z"
    symbol: AAPL
    shares: 10
    price: 100.0
    amount: 1000.0
    currency: USD
  - id: "33333333-3333-3333-3333-333333333333"
    type: dividend
    date: "2026-03-01T00:00:00Z"
    symbol: AAPL
    amount: 5.0
    currency: USD
"""


async def _setup(hass, investments_dir):
    investments_dir.write_portfolio(cash_balance=0.0)
    investments_dir.write_transactions(raw_yaml=TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_diagnostics_includes_repository_and_provider_identity(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["repository"]["name"] == "yaml"
    assert diagnostics["repository"]["supports_transactions"] is True
    assert diagnostics["providers"]["price_provider"] == "yahoo_finance"
    assert diagnostics["providers"]["currency_provider"] == "yahoo_finance"
    assert diagnostics["providers"]["snapshot_repository"] == "store"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_calculator_registry(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    calculators = diagnostics["calculators"]
    assert len(calculators) == 11
    assert calculators["summary"] == "PortfolioCalculator"
    assert calculators["twr"] == "TwrCalculator"
    assert calculators["concentration"] == "PositionAnalyticsCalculator"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_environment_info(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    env = diagnostics["environment"]
    assert env["engine_version"] == "1.0.0"
    assert env["integration_version"] is not None
    assert env["home_assistant_core_version"] is not None
    assert env["minimum_supported_home_assistant_version"] == "2025.1"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_snapshot_statistics_expanded(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    snapshots = diagnostics["snapshots"]
    assert snapshots["count"] == 1  # first-ever refresh creates exactly one
    assert snapshots["oldest_timestamp"] is not None
    assert snapshots["latest_timestamp"] is not None
    assert snapshots["span_days"] == 0  # only one snapshot so far
    assert snapshots["created_this_refresh"] is True

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_transaction_statistics(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    transactions = diagnostics["transactions"]
    assert transactions["count"] == 3
    assert transactions["count_by_type"] == {"deposit": 1, "buy": 1, "dividend": 1}
    assert transactions["oldest_date"] is not None
    assert transactions["latest_date"] is not None
    assert transactions["oldest_date"] < transactions["latest_date"]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_transaction_statistics_empty_log(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)  # no transactions.yaml

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["transactions"] == {
        "count": 0,
        "count_by_type": {},
        "oldest_date": None,
        "latest_date": None,
    }

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_includes_benchmarks_reference(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    entry = await _setup(hass, investments_dir)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["benchmarks"]["see"] == "BENCHMARKS.md"
    assert diagnostics["benchmarks"]["engine_version"] == "1.0.0"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_still_redacts_investments_path(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    """No secrets, per the milestone's own requirement - confirms the
    Milestone 8 expansion didn't accidentally weaken existing redaction.
    """
    entry = await _setup(hass, investments_dir)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"]["investments_path"] == "**REDACTED**"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
