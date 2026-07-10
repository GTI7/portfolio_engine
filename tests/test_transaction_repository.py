from pathlib import Path

import pytest
import yaml

from repositories.yaml_repository import YamlRepository


def write_holdings(portfolio_dir: Path, **overrides):
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    content = overrides.pop(
        "raw",
        "name: Test Portfolio\nbase_currency: USD\nholdings:\n"
        "  - symbol: AAPL\n    shares: 10\n    avg_price: 100\n"
        "    currency: USD\n    type: stock\n",
    )
    (portfolio_dir / "holdings.yaml").write_text(content)


def write_transactions(portfolio_dir: Path, raw: str):
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    (portfolio_dir / "transactions.yaml").write_text(raw)


VALID_TRANSACTIONS_YAML = """
transactions:
  - id: "11111111-1111-1111-1111-111111111111"
    type: buy
    date: "2026-03-15T14:30:00Z"
    symbol: AAPL
    shares: 10
    price: 100.0
    amount: 1000.0
    currency: USD
    notes: "Initial position"

  - id: "22222222-2222-2222-2222-222222222222"
    type: dividend
    date: "2026-04-01T00:00:00Z"
    symbol: AAPL
    amount: 12.5
    currency: USD

  - id: "33333333-3333-3333-3333-333333333333"
    type: deposit
    date: "2026-01-01T00:00:00Z"
    amount: 5000.0
    currency: USD
"""


@pytest.mark.asyncio
async def test_portfolio_without_transactions_file_gets_empty_list(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)

    repo = YamlRepository(tmp_path)
    portfolios = await repo.async_get_portfolios()

    assert len(portfolios) == 1
    assert portfolios[0].transactions == []


@pytest.mark.asyncio
async def test_transactions_loaded_and_populated_on_portfolio(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    write_transactions(portfolio_dir, VALID_TRANSACTIONS_YAML)

    repo = YamlRepository(tmp_path)
    portfolios = await repo.async_get_portfolios()

    assert len(portfolios[0].transactions) == 3
    types = {t.type.value for t in portfolios[0].transactions}
    assert types == {"buy", "dividend", "deposit"}


@pytest.mark.asyncio
async def test_transactions_sorted_chronologically_regardless_of_file_order(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    # VALID_TRANSACTIONS_YAML lists buy (Mar), dividend (Apr), deposit (Jan)
    # in that file order - chronological order should be deposit, buy, dividend.
    write_transactions(portfolio_dir, VALID_TRANSACTIONS_YAML)

    repo = YamlRepository(tmp_path)
    transactions = await repo.async_get_transactions("demo")

    assert [t.type.value for t in transactions] == ["deposit", "buy", "dividend"]
    assert transactions[0].date < transactions[1].date < transactions[2].date


@pytest.mark.asyncio
async def test_async_get_transactions_directly_without_full_portfolio_load(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    write_transactions(portfolio_dir, VALID_TRANSACTIONS_YAML)

    repo = YamlRepository(tmp_path)
    transactions = await repo.async_get_transactions("demo")

    assert len(transactions) == 3


@pytest.mark.asyncio
async def test_missing_transactions_file_via_async_get_transactions(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)

    repo = YamlRepository(tmp_path)
    transactions = await repo.async_get_transactions("demo")

    assert transactions == []


@pytest.mark.asyncio
async def test_get_transactions_for_nonexistent_portfolio_id(tmp_path):
    repo = YamlRepository(tmp_path)
    transactions = await repo.async_get_transactions("does_not_exist")
    assert transactions == []


@pytest.mark.asyncio
async def test_duplicate_transaction_ids_raise(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    duplicate_yaml = """
transactions:
  - id: "11111111-1111-1111-1111-111111111111"
    type: deposit
    date: "2026-01-01T00:00:00Z"
    amount: 100.0
    currency: USD
  - id: "11111111-1111-1111-1111-111111111111"
    type: deposit
    date: "2026-01-02T00:00:00Z"
    amount: 200.0
    currency: USD
"""
    write_transactions(portfolio_dir, duplicate_yaml)

    repo = YamlRepository(tmp_path)
    with pytest.raises(ValueError, match="duplicate transaction id"):
        await repo.async_get_portfolios()


@pytest.mark.asyncio
async def test_malformed_yaml_raises(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    write_transactions(portfolio_dir, "transactions: [this is: not, valid: yaml: at all")

    repo = YamlRepository(tmp_path)
    with pytest.raises(yaml.YAMLError):  # malformed YAML is a parse failure
        await repo.async_get_portfolios()


@pytest.mark.asyncio
async def test_invalid_transaction_data_raises_via_model_validation(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    invalid_yaml = """
transactions:
  - id: "11111111-1111-1111-1111-111111111111"
    type: buy
    date: "2026-01-01T00:00:00Z"
    amount: 100.0
    currency: USD
"""  # buy requires symbol/shares/price - none given
    write_transactions(portfolio_dir, invalid_yaml)

    repo = YamlRepository(tmp_path)
    with pytest.raises(ValueError, match="requires symbol"):
        await repo.async_get_portfolios()


@pytest.mark.asyncio
async def test_unknown_transaction_type_raises(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    invalid_yaml = """
transactions:
  - id: "11111111-1111-1111-1111-111111111111"
    type: not_a_real_type
    date: "2026-01-01T00:00:00Z"
    amount: 100.0
    currency: USD
"""
    write_transactions(portfolio_dir, invalid_yaml)

    repo = YamlRepository(tmp_path)
    with pytest.raises(ValueError):
        await repo.async_get_portfolios()


@pytest.mark.asyncio
async def test_transaction_id_generated_when_omitted(tmp_path):
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)
    no_id_yaml = """
transactions:
  - type: deposit
    date: "2026-01-01T00:00:00Z"
    amount: 100.0
    currency: USD
"""
    write_transactions(portfolio_dir, no_id_yaml)

    repo = YamlRepository(tmp_path)
    transactions = await repo.async_get_transactions("demo")

    assert len(transactions) == 1
    assert transactions[0].id  # non-empty, generated


@pytest.mark.asyncio
async def test_backward_compatibility_existing_fixtures_unaffected(tmp_path):
    """Every pre-Milestone-4 repository fixture (no transactions.yaml at
    all) must behave identically to before this milestone.
    """
    portfolio_dir = tmp_path / "demo"
    write_holdings(portfolio_dir)

    repo = YamlRepository(tmp_path)
    portfolios = await repo.async_get_portfolios()

    assert len(portfolios) == 1
    assert portfolios[0].transactions == []
    assert len(portfolios[0].holdings) == 1
    assert repo.supports_transactions is True
