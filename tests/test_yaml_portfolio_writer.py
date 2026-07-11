from datetime import UTC, datetime

import pytest
import yaml

from engine.models import Holding, Transaction, TransactionType
from repositories.yaml_portfolio_writer import YamlPortfolioWriter


def _txn(txn_id: str, amount: float = 100.0) -> Transaction:
    return Transaction(
        id=txn_id,
        portfolio_id="demo_portfolio",
        type=TransactionType.DEPOSIT,
        date=datetime(2026, 1, 1, tzinfo=UTC),
        currency="USD",
        amount=amount,
    )


@pytest.mark.asyncio
async def test_create_portfolio_writes_holdings_yaml_with_expected_shape(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    holdings = [Holding(symbol="AAPL", shares=10, avg_price=150.0, currency="USD", type="stock")]

    await writer.async_create_portfolio("demo_portfolio", "Demo", "USD", 500.0, holdings)

    data = yaml.safe_load((tmp_path / "demo_portfolio" / "holdings.yaml").read_text())
    assert data["name"] == "Demo"
    assert data["base_currency"] == "USD"
    assert data["cash_balance"] == 500.0
    assert data["holdings"] == [
        {"symbol": "AAPL", "shares": 10, "avg_price": 150.0, "currency": "USD", "type": "stock"}
    ]


@pytest.mark.asyncio
async def test_create_portfolio_with_empty_holdings_list(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_create_portfolio("empty_portfolio", "Empty", "EUR", 0.0, [])

    data = yaml.safe_load((tmp_path / "empty_portfolio" / "holdings.yaml").read_text())
    assert data["holdings"] == []


@pytest.mark.asyncio
async def test_create_portfolio_includes_account_when_set(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    holdings = [
        Holding(
            symbol="AAPL", shares=10, avg_price=150.0, currency="USD", type="stock", account="ibkr"
        )
    ]
    await writer.async_create_portfolio("demo_portfolio", "Demo", "USD", 0.0, holdings)

    data = yaml.safe_load((tmp_path / "demo_portfolio" / "holdings.yaml").read_text())
    assert data["holdings"][0]["account"] == "ibkr"


@pytest.mark.asyncio
async def test_create_portfolio_raises_if_holdings_yaml_already_exists(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_create_portfolio("demo_portfolio", "Demo", "USD", 0.0, [])

    with pytest.raises(FileExistsError):
        await writer.async_create_portfolio("demo_portfolio", "Demo Again", "USD", 0.0, [])

    # The original file must be untouched by the rejected second attempt.
    data = yaml.safe_load((tmp_path / "demo_portfolio" / "holdings.yaml").read_text())
    assert data["name"] == "Demo"


@pytest.mark.asyncio
async def test_append_transactions_to_new_file_creates_transactions_yaml(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_append_transactions("demo_portfolio", [_txn("t1")])

    data = yaml.safe_load((tmp_path / "demo_portfolio" / "transactions.yaml").read_text())
    assert [t["id"] for t in data["transactions"]] == ["t1"]


@pytest.mark.asyncio
async def test_append_transactions_never_rewrites_existing_rows(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_append_transactions("demo_portfolio", [_txn("t1"), _txn("t2")])
    await writer.async_append_transactions("demo_portfolio", [_txn("t3")])

    data = yaml.safe_load((tmp_path / "demo_portfolio" / "transactions.yaml").read_text())
    assert [t["id"] for t in data["transactions"]] == ["t1", "t2", "t3"]


@pytest.mark.asyncio
async def test_atomic_replace_uses_temp_file_in_same_directory(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_create_portfolio("demo_portfolio", "Demo", "USD", 0.0, [])

    remaining = list((tmp_path / "demo_portfolio").iterdir())
    assert all(not p.name.endswith(".tmp") for p in remaining)


@pytest.mark.asyncio
async def test_bak_file_is_created_on_second_write_and_holds_prior_content(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_append_transactions("demo_portfolio", [_txn("t1")])
    first_content = (tmp_path / "demo_portfolio" / "transactions.yaml").read_text()

    await writer.async_append_transactions("demo_portfolio", [_txn("t2")])

    bak_path = tmp_path / "demo_portfolio" / "transactions.yaml.bak"
    assert bak_path.exists()
    assert bak_path.read_text() == first_content


@pytest.mark.asyncio
async def test_bak_file_is_overwritten_not_accumulated_on_third_write(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_append_transactions("demo_portfolio", [_txn("t1")])
    await writer.async_append_transactions("demo_portfolio", [_txn("t2")])
    second_content = (tmp_path / "demo_portfolio" / "transactions.yaml").read_text()

    await writer.async_append_transactions("demo_portfolio", [_txn("t3")])

    bak_path = tmp_path / "demo_portfolio" / "transactions.yaml.bak"
    assert bak_path.read_text() == second_content
    # Still exactly one .bak file - no accumulated history.
    bak_files = list((tmp_path / "demo_portfolio").glob("transactions.yaml.bak*"))
    assert len(bak_files) == 1


@pytest.mark.asyncio
async def test_no_bak_file_on_the_very_first_write(tmp_path):
    writer = YamlPortfolioWriter(tmp_path)
    await writer.async_create_portfolio("demo_portfolio", "Demo", "USD", 0.0, [])

    bak_path = tmp_path / "demo_portfolio" / "holdings.yaml.bak"
    assert not bak_path.exists()


def test_writer_name_property():
    writer = YamlPortfolioWriter("/some/path")
    assert writer.name == "yaml"
