"""Activates the pytest-homeassistant-custom-component plugin (registers the
`hass`, `enable_custom_integrations`, etc. fixtures) for this test package
only — kept separate from the root conftest.py (which serves the plain
`tests/` engine suite and doesn't need, and shouldn't pull in, a full HA
install).

Run with the dedicated venv that has `homeassistant` +
`pytest-homeassistant-custom-component` installed — see
MILESTONE_2_5.md for the exact command. These tests are NOT run by the
plain `pip install -r requirements-test.txt` flow used for tests/ and
tests_integration/, intentionally: this is a much heavier dependency than
the rest of the project needs.
"""
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytest_plugins = "pytest_homeassistant_custom_component"

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_price_provider():
    """Patch YahooFinanceProvider.async_get_quotes so tests that exercise a
    full config-entry setup (which triggers a real coordinator refresh) get
    deterministic, instant quotes instead of a real network call.

    Also patches `async_get_clientsession` used by the coordinator: merely
    *constructing* a real aiohttp ClientSession (even one that's never used,
    because the quotes call above is mocked) leaves a background cleanup
    thread running past test teardown in this environment, which the HA
    test harness's cleanup verification correctly flags as a leak. Real
    aiohttp session behavior is exactly the kind of thing that needs
    validating against a real HA instance instead — see MILESTONE_2_5.md.
    """
    from unittest.mock import MagicMock

    from custom_components.portfolio_engine.engine.models import Quote

    async def _fake_get_quotes(self, symbols):
        return {
            symbol: Quote(symbol=symbol, price=150.0, currency="USD", change_pct=1.5)
            for symbol in symbols
        }

    with (
        patch(
            "custom_components.portfolio_engine.providers.yahoo_finance."
            "YahooFinanceProvider.async_get_quotes",
            new=_fake_get_quotes,
        ),
        patch(
            "custom_components.portfolio_engine.coordinator.async_get_clientsession",
            new=MagicMock(return_value=MagicMock()),
        ),
    ):
        yield


@pytest.fixture
def mock_currency_provider():
    """Patch YahooFinanceCurrencyProvider.async_get_rates with a fixed
    USD->EUR rate, for tests exercising a multi-currency portfolio through
    a full config-entry setup. Kept separate from mock_price_provider so
    single-currency tests (the majority) don't need to know this exists -
    it's opt-in only for the multi-currency test(s) that need it.
    """

    async def _fake_get_rates(self, base, targets):
        rates = {base: 1.0}
        rates.update({t: 0.92 for t in targets if t == "USD"})
        return rates

    with patch(
        "custom_components.portfolio_engine.providers.yahoo_finance_currency."
        "YahooFinanceCurrencyProvider.async_get_rates",
        new=_fake_get_rates,
    ):
        yield


@pytest.fixture
def investments_dir(tmp_path: Path):
    """A fresh, per-test investments folder. Returned as a helper object
    with `.path` (str, for use as `investments_path` in config entry data —
    passed as an *absolute* path, which `hass.config.path()` respects and
    returns unchanged regardless of `hass.config.config_dir`) and
    `.write_portfolio(...)` to populate it.
    """

    class _InvestmentsDir:
        def __init__(self, root: Path) -> None:
            self._root = root
            self.path = str(root)

        def write_portfolio(
            self,
            portfolio_id: str = "demo_portfolio",
            *,
            name: str = "Demo Portfolio",
            base_currency: str = "USD",
            cash_balance: float = 1000.0,
            holdings: list[dict] | None = None,
            raw_yaml: str | None = None,
        ) -> Path:
            portfolio_dir = self._root / portfolio_id
            portfolio_dir.mkdir(parents=True, exist_ok=True)
            holdings_file = portfolio_dir / "holdings.yaml"
            if raw_yaml is not None:
                holdings_file.write_text(raw_yaml)
            else:
                data = {
                    "name": name,
                    "base_currency": base_currency,
                    "cash_balance": cash_balance,
                    "holdings": holdings
                    or [
                        {
                            "symbol": "AAPL",
                            "shares": 10,
                            "avg_price": 100.0,
                            "currency": "USD",
                            "type": "stock",
                        }
                    ],
                }
                holdings_file.write_text(yaml.safe_dump(data))
            return holdings_file

        def write_transactions(
            self, portfolio_id: str = "demo_portfolio", *, raw_yaml: str
        ) -> Path:
            """Milestone 4 — writes transactions.yaml alongside an existing
            portfolio directory (call write_portfolio first). Kept as a
            distinct method, not a write_portfolio parameter, matching how
            the real repository treats holdings.yaml/transactions.yaml as
            separate files.
            """
            portfolio_dir = self._root / portfolio_id
            portfolio_dir.mkdir(parents=True, exist_ok=True)
            transactions_file = portfolio_dir / "transactions.yaml"
            transactions_file.write_text(raw_yaml)
            return transactions_file

    investments_root = tmp_path / "investments"
    investments_root.mkdir(parents=True, exist_ok=True)
    return _InvestmentsDir(investments_root)
