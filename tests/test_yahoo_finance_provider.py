import pytest

from providers.yahoo_finance import YahooFinanceProvider

FAKE_RESPONSE = {
    "quoteResponse": {
        "result": [
            {
                "symbol": "AAPL",
                "regularMarketPrice": 195.32,
                "currency": "USD",
                "regularMarketChangePercent": 1.25,
                "longName": "Apple Inc.",
            },
            {
                "symbol": "MSFT",
                "regularMarketPrice": 421.10,
                "currency": "USD",
                "regularMarketChangePercent": -0.42,
                "shortName": "Microsoft",
            },
        ]
    }
}


async def fake_fetch(url: str) -> dict:
    assert "AAPL" in url and "MSFT" in url
    return FAKE_RESPONSE


@pytest.mark.asyncio
async def test_batches_symbols_into_one_call():
    calls = []

    async def counting_fetch(url: str) -> dict:
        calls.append(url)
        return FAKE_RESPONSE

    provider = YahooFinanceProvider(fetch=counting_fetch)
    quotes = await provider.async_get_quotes(["AAPL", "MSFT"])

    assert len(calls) == 1  # one HTTP call for both symbols, not two
    assert set(quotes.keys()) == {"AAPL", "MSFT"}
    assert quotes["AAPL"].price == 195.32
    assert quotes["AAPL"].name == "Apple Inc."
    assert quotes["MSFT"].change_pct == -0.42


@pytest.mark.asyncio
async def test_empty_symbol_list_skips_fetch():
    async def should_not_be_called(url: str) -> dict:
        raise AssertionError("fetch should not be called for an empty symbol list")

    provider = YahooFinanceProvider(fetch=should_not_be_called)
    quotes = await provider.async_get_quotes([])
    assert quotes == {}


@pytest.mark.asyncio
async def test_unknown_symbol_in_response_is_skipped_not_raised():
    async def fetch_with_junk(url: str) -> dict:
        return {"quoteResponse": {"result": [{"regularMarketPrice": 1.0}]}}  # no symbol key

    provider = YahooFinanceProvider(fetch=fetch_with_junk)
    quotes = await provider.async_get_quotes(["AAPL"])
    assert quotes == {}
