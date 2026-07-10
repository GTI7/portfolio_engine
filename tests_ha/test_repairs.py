"""Milestone 8 — Repairs framework integration tests: reconciliation
discrepancy, missing FX rates, snapshot repository unavailable, malformed
transaction history. Each condition: create when present, clear when
resolved.
"""
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)

MISMATCHED_TRANSACTIONS_YAML = """
transactions:
  - id: "aaaaaaaa-1111-1111-1111-111111111111"
    type: deposit
    date: "2025-12-31T00:00:00Z"
    amount: 1000.0
    currency: USD
  - id: "bbbbbbbb-2222-2222-2222-222222222222"
    type: buy
    date: "2026-01-01T00:00:00Z"
    symbol: AAPL
    shares: 5
    price: 100.0
    amount: 500.0
    currency: USD
"""

MATCHING_TRANSACTIONS_YAML = """
transactions:
  - id: "cccccccc-3333-3333-3333-333333333333"
    type: deposit
    date: "2025-12-31T00:00:00Z"
    amount: 1000.0
    currency: USD
  - id: "dddddddd-4444-4444-4444-444444444444"
    type: buy
    date: "2026-01-01T00:00:00Z"
    symbol: AAPL
    shares: 10
    price: 100.0
    amount: 1000.0
    currency: USD
"""


async def test_reconciliation_discrepancy_creates_and_clears_issue(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    # holdings.yaml declares the default 10 shares, but the log only shows 5 -> discrepancy
    investments_dir.write_portfolio(cash_balance=0.0)
    investments_dir.write_transactions(raw_yaml=MISMATCHED_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = ir.async_get(hass)
    issue = registry.async_get_issue(DOMAIN, f"{entry.entry_id}_reconciliation_discrepancy")
    assert issue is not None
    assert issue.translation_key == "reconciliation_discrepancy"

    # now fix the transaction log to match declared holdings and refresh again
    investments_dir.write_transactions(raw_yaml=MATCHING_TRANSACTIONS_YAML)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    issue_after = registry.async_get_issue(DOMAIN, f"{entry.entry_id}_reconciliation_discrepancy")
    assert issue_after is None  # cleared once resolved

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def _fake_rates_missing(self, base, targets):
    return {base: 1.0}  # never returns a rate for any target currency


async def _fake_rates_ok(self, base, targets):
    rates = {base: 1.0}
    rates.update({t: 0.92 for t in targets})
    return rates


async def test_missing_fx_rates_creates_and_clears_issue(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(
        base_currency="EUR",
        cash_balance=0.0,
        holdings=[
            {"symbol": "AAPL", "shares": 10, "avg_price": 100.0, "currency": "USD", "type": "stock"}
        ],
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.portfolio_engine.providers.yahoo_finance_currency."
        "YahooFinanceCurrencyProvider.async_get_rates",
        new=_fake_rates_missing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = ir.async_get(hass)
        issue = registry.async_get_issue(DOMAIN, f"{entry.entry_id}_missing_fx_rates")
        assert issue is not None
        assert issue.translation_placeholders["currencies"] == "USD"

    # now the rate becomes available and we refresh again
    with patch(
        "custom_components.portfolio_engine.providers.yahoo_finance_currency."
        "YahooFinanceCurrencyProvider.async_get_rates",
        new=_fake_rates_ok,
    ):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    registry = ir.async_get(hass)
    issue_after = registry.async_get_issue(DOMAIN, f"{entry.entry_id}_missing_fx_rates")
    assert issue_after is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def _broken_get_snapshots(self, portfolio_id):
    raise RuntimeError("simulated Store failure")


async def test_snapshot_repository_unavailable_creates_and_clears_issue(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.portfolio_engine.store_snapshot_repository."
        "StoreSnapshotRepository.async_get_snapshots",
        new=_broken_get_snapshots,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = ir.async_get(hass)
        issue = registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_snapshot_repository_unavailable"
        )
        assert issue is not None
        # setup still succeeded despite the broken snapshot storage
        assert hass.states.get("sensor.demo_portfolio_value").state != "unavailable"

    # storage recovers on the next refresh
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    registry = ir.async_get(hass)
    issue_after = registry.async_get_issue(
        DOMAIN, f"{entry.entry_id}_snapshot_repository_unavailable"
    )
    assert issue_after is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_malformed_transaction_history_creates_issue(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=1000.0)
    # buy requires symbol/shares/price - none given, fails Transaction validation
    invalid_yaml = """
transactions:
  - id: "eeeeeeee-5555-5555-5555-555555555555"
    type: buy
    date: "2026-01-01T00:00:00Z"
    amount: 100.0
    currency: USD
"""
    investments_dir.write_transactions(raw_yaml=invalid_yaml)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    # setup itself will fail (ConfigEntryNotReady territory) since the very
    # first refresh hits the malformed data - confirm it doesn't crash HA
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is False  # setup did not succeed, as expected

    registry = ir.async_get(hass)
    issue = registry.async_get_issue(DOMAIN, f"{entry.entry_id}_malformed_transaction_history")
    assert issue is not None
    assert "requires symbol" in issue.translation_placeholders["error"]


async def test_issues_cleaned_up_on_unload(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio(cash_balance=0.0)
    investments_dir.write_transactions(raw_yaml=MISMATCHED_TRANSACTIONS_YAML)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = ir.async_get(hass)
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_reconciliation_discrepancy")
        is not None
    )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get_issue(DOMAIN, f"{entry.entry_id}_reconciliation_discrepancy") is None
