from pathlib import Path

import pytest

from repositories.yaml_repository import YamlRepository

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"


@pytest.mark.asyncio
async def test_loads_demo_portfolio():
    repo = YamlRepository(SAMPLE_DATA)
    portfolios = await repo.async_get_portfolios()

    assert len(portfolios) == 1
    demo = portfolios[0]
    assert demo.id == "demo_portfolio"
    assert demo.name == "Demo Portfolio"
    assert demo.base_currency == "USD"
    assert len(demo.holdings) == 3
    assert {h.symbol for h in demo.holdings} == {"AAPL", "MSFT", "BTC-USD"}


@pytest.mark.asyncio
async def test_missing_directory_returns_empty_list(tmp_path):
    repo = YamlRepository(tmp_path / "does_not_exist")
    portfolios = await repo.async_get_portfolios()
    assert portfolios == []


@pytest.mark.asyncio
async def test_portfolio_dir_without_holdings_file_is_skipped(tmp_path):
    empty_dir = tmp_path / "empty_portfolio"
    empty_dir.mkdir()
    repo = YamlRepository(tmp_path)
    portfolios = await repo.async_get_portfolios()
    assert portfolios == []


@pytest.mark.asyncio
async def test_invalid_holding_raises(tmp_path):
    portfolio_dir = tmp_path / "bad_portfolio"
    portfolio_dir.mkdir()
    (portfolio_dir / "holdings.yaml").write_text(
        "name: Bad\nholdings:\n  - symbol: XXX\n    shares: -5\n    avg_price: 1\n    "
        "currency: USD\n    type: stock\n"
    )
    repo = YamlRepository(tmp_path)
    with pytest.raises(ValueError):
        await repo.async_get_portfolios()
