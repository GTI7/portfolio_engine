import pytest

from providers.yahoo_finance_currency import YahooFinanceCurrencyProvider

FAKE_RESPONSE = {
    "quoteResponse": {
        "result": [
            {"symbol": "USDEUR=X", "regularMarketPrice": 0.92},
            {"symbol": "GBPEUR=X", "regularMarketPrice": 1.17},
        ]
    }
}


@pytest.mark.asyncio
async def test_returns_base_currency_at_rate_one_without_a_call():
    async def should_not_be_called(url: str) -> dict:
        raise AssertionError("fetch should not be called when base == only target")

    provider = YahooFinanceCurrencyProvider(fetch=should_not_be_called)
    rates = await provider.async_get_rates("EUR", ["EUR"])
    assert rates == {"EUR": 1.0}


@pytest.mark.asyncio
async def test_batches_targets_into_one_call():
    calls = []

    async def counting_fetch(url: str) -> dict:
        calls.append(url)
        return FAKE_RESPONSE

    provider = YahooFinanceCurrencyProvider(fetch=counting_fetch)
    rates = await provider.async_get_rates("EUR", ["USD", "GBP"])

    assert len(calls) == 1
    assert "USDEUR=X" in calls[0] and "GBPEUR=X" in calls[0]
    assert rates == {"EUR": 1.0, "USD": 0.92, "GBP": 1.17}


@pytest.mark.asyncio
async def test_empty_targets_list_skips_fetch():
    async def should_not_be_called(url: str) -> dict:
        raise AssertionError("fetch should not be called for an empty target list")

    provider = YahooFinanceCurrencyProvider(fetch=should_not_be_called)
    rates = await provider.async_get_rates("EUR", [])
    assert rates == {"EUR": 1.0}


@pytest.mark.asyncio
async def test_missing_rate_in_response_is_simply_absent_not_raised():
    async def fetch_partial(url: str) -> dict:
        return {"quoteResponse": {"result": [{"symbol": "USDEUR=X", "regularMarketPrice": 0.92}]}}

    provider = YahooFinanceCurrencyProvider(fetch=fetch_partial)
    rates = await provider.async_get_rates("EUR", ["USD", "GBP"])
    assert rates == {"EUR": 1.0, "USD": 0.92}  # GBP simply missing, not an error
