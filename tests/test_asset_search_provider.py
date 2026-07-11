import pytest

from providers.yahoo_finance_asset_search import YahooFinanceAssetSearchProvider

# Shapes frozen from the actually-verified live Yahoo Finance search API
# (query1.finance.yahoo.com/v1/finance/search), checked before writing this
# provider - see MILESTONE_11_DESIGN.md and ADR-0014. No test here makes a
# real network call; these are recorded response shapes, not live calls.
APPLE_SEARCH_RESPONSE = {
    "quotes": [
        {
            "symbol": "AAPL",
            "shortname": "Apple Inc.",
            "exchange": "NMS",
            "exchDisp": "NASDAQ",
            "quoteType": "EQUITY",
        },
        {
            "symbol": "APLE",
            "shortname": "Apple Hospitality REIT",
            "exchange": "NYQ",
            "exchDisp": "NYSE",
            "quoteType": "EQUITY",
        },
    ]
}
APPLE_QUOTE_RESPONSE = {
    "quoteResponse": {
        "result": [
            {"symbol": "AAPL", "currency": "USD"},
            {"symbol": "APLE", "currency": "USD"},
        ]
    }
}

VANGUARD_SEARCH_RESPONSE = {
    "quotes": [
        {
            "symbol": "VWCE.DE",
            "longname": "Vanguard FTSE All-World UCITS ETF USD Accumulation",
            "exchange": "GER",
            "exchDisp": "XETRA",
            "quoteType": "ETF",
        },
        {
            "symbol": "VEU",
            "longname": "Vanguard FTSE All-World ex-US Index Fund ETF Shares",
            "exchange": "PCX",
            "exchDisp": "NYSEArca",
            "quoteType": "ETF",
        },
    ]
}
VANGUARD_QUOTE_RESPONSE = {
    "quoteResponse": {
        "result": [
            {"symbol": "VWCE.DE", "currency": "EUR"},
            {"symbol": "VEU", "currency": "USD"},
        ]
    }
}


def _fetchers(search_response, quote_response, search_calls=None, quote_calls=None):
    async def search_fetch(url: str) -> dict:
        if search_calls is not None:
            search_calls.append(url)
        return search_response

    async def quote_fetch(url: str) -> dict:
        if quote_calls is not None:
            quote_calls.append(url)
        return quote_response

    return search_fetch, quote_fetch


@pytest.mark.asyncio
async def test_empty_query_skips_both_fetches():
    async def should_not_be_called(url: str) -> dict:
        raise AssertionError("fetch should not be called for an empty query")

    provider = YahooFinanceAssetSearchProvider(
        search_fetch=should_not_be_called, quote_fetch=should_not_be_called
    )
    assert await provider.async_search("") == []


@pytest.mark.asyncio
async def test_zero_or_negative_limit_skips_both_fetches():
    async def should_not_be_called(url: str) -> dict:
        raise AssertionError("fetch should not be called for a non-positive limit")

    provider = YahooFinanceAssetSearchProvider(
        search_fetch=should_not_be_called, quote_fetch=should_not_be_called
    )
    assert await provider.async_search("apple", limit=0) == []
    assert await provider.async_search("apple", limit=-5) == []


@pytest.mark.asyncio
async def test_real_worked_example_apple():
    search_fetch, quote_fetch = _fetchers(APPLE_SEARCH_RESPONSE, APPLE_QUOTE_RESPONSE)
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("Apple")

    assert len(results) == 2
    aapl = next(r for r in results if r.symbol == "AAPL")
    assert aapl.name == "Apple Inc."
    assert aapl.exchange == "NASDAQ"
    assert aapl.currency == "USD"
    assert aapl.asset_type == "stock"


@pytest.mark.asyncio
async def test_real_worked_example_vanguard_ftse_all_world():
    search_fetch, quote_fetch = _fetchers(VANGUARD_SEARCH_RESPONSE, VANGUARD_QUOTE_RESPONSE)
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("Vanguard FTSE All-World")

    vwce = next(r for r in results if r.symbol == "VWCE.DE")
    assert vwce.name == "Vanguard FTSE All-World UCITS ETF USD Accumulation"
    assert vwce.exchange == "XETRA"
    assert vwce.currency == "EUR"
    assert vwce.asset_type == "etf"


@pytest.mark.asyncio
async def test_maps_equity_etf_mutualfund_crypto_to_project_vocabulary():
    search_response = {
        "quotes": [
            {
                "symbol": "AAPL",
                "shortname": "Apple Inc.",
                "exchDisp": "NASDAQ",
                "quoteType": "EQUITY",
            },
            {
                "symbol": "VWCE.DE",
                "shortname": "Vanguard ETF",
                "exchDisp": "XETRA",
                "quoteType": "ETF",
            },
            {
                "symbol": "VTSAX",
                "shortname": "Vanguard Total Stock",
                "exchDisp": "NASDAQ",
                "quoteType": "MUTUALFUND",
            },
            {
                "symbol": "BTC-USD",
                "shortname": "Bitcoin USD",
                "exchDisp": "CCC",
                "quoteType": "CRYPTOCURRENCY",
            },
        ]
    }
    quote_response = {
        "quoteResponse": {
            "result": [
                {"symbol": "AAPL", "currency": "USD"},
                {"symbol": "VWCE.DE", "currency": "EUR"},
                {"symbol": "VTSAX", "currency": "USD"},
                {"symbol": "BTC-USD", "currency": "USD"},
            ]
        }
    }
    search_fetch, quote_fetch = _fetchers(search_response, quote_response)
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("vanguard")

    by_symbol = {r.symbol: r.asset_type for r in results}
    assert by_symbol == {
        "AAPL": "stock",
        "VWCE.DE": "etf",
        "VTSAX": "mutual_fund",
        "BTC-USD": "crypto",
    }


@pytest.mark.asyncio
async def test_unsupported_quote_types_are_filtered_out_before_the_quote_call():
    search_response = {
        "quotes": [
            {
                "symbol": "AAPL",
                "shortname": "Apple Inc.",
                "exchDisp": "NASDAQ",
                "quoteType": "EQUITY",
            },
            {"symbol": "^GSPC", "shortname": "S&P 500", "exchDisp": "SNP", "quoteType": "INDEX"},
            {"symbol": "CL=F", "shortname": "Crude Oil", "exchDisp": "NYM", "quoteType": "FUTURE"},
        ]
    }
    quote_calls: list[str] = []
    search_fetch, quote_fetch = _fetchers(
        search_response,
        {"quoteResponse": {"result": [{"symbol": "AAPL", "currency": "USD"}]}},
        quote_calls=quote_calls,
    )
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("apple")

    assert [r.symbol for r in results] == ["AAPL"]
    assert "^GSPC" not in quote_calls[0]
    assert "CL=F" not in quote_calls[0]


@pytest.mark.asyncio
async def test_batches_currency_enrichment_into_one_call():
    search_calls: list[str] = []
    quote_calls: list[str] = []
    search_fetch, quote_fetch = _fetchers(
        VANGUARD_SEARCH_RESPONSE,
        VANGUARD_QUOTE_RESPONSE,
        search_calls=search_calls,
        quote_calls=quote_calls,
    )
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    await provider.async_search("Vanguard FTSE All-World")

    assert len(search_calls) == 1
    assert len(quote_calls) == 1
    assert "VWCE.DE" in quote_calls[0] and "VEU" in quote_calls[0]


@pytest.mark.asyncio
async def test_missing_currency_in_enrichment_response_drops_that_candidate_not_raised():
    quote_response = {"quoteResponse": {"result": [{"symbol": "VWCE.DE", "currency": "EUR"}]}}
    search_fetch, quote_fetch = _fetchers(VANGUARD_SEARCH_RESPONSE, quote_response)
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("Vanguard FTSE All-World")

    assert [r.symbol for r in results] == ["VWCE.DE"]  # VEU dropped, not an error


@pytest.mark.asyncio
async def test_malformed_search_item_missing_symbol_is_skipped():
    search_response = {
        "quotes": [
            {"shortname": "No symbol here", "exchDisp": "NASDAQ", "quoteType": "EQUITY"},
            {
                "symbol": "AAPL",
                "shortname": "Apple Inc.",
                "exchDisp": "NASDAQ",
                "quoteType": "EQUITY",
            },
        ]
    }
    quote_response = {"quoteResponse": {"result": [{"symbol": "AAPL", "currency": "USD"}]}}
    search_fetch, quote_fetch = _fetchers(search_response, quote_response)
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("apple")

    assert [r.symbol for r in results] == ["AAPL"]


@pytest.mark.asyncio
async def test_uses_longname_falling_back_to_shortname_falling_back_to_symbol():
    search_response = {
        "quotes": [
            {"symbol": "A", "longname": "Has Long Name", "exchDisp": "X", "quoteType": "EQUITY"},
            {"symbol": "B", "shortname": "Has Short Name", "exchDisp": "X", "quoteType": "EQUITY"},
            {"symbol": "C", "exchDisp": "X", "quoteType": "EQUITY"},
        ]
    }
    quote_response = {
        "quoteResponse": {
            "result": [
                {"symbol": "A", "currency": "USD"},
                {"symbol": "B", "currency": "USD"},
                {"symbol": "C", "currency": "USD"},
            ]
        }
    }
    search_fetch, quote_fetch = _fetchers(search_response, quote_response)
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("x")
    by_symbol = {r.symbol: r.name for r in results}

    assert by_symbol == {"A": "Has Long Name", "B": "Has Short Name", "C": "C"}


@pytest.mark.asyncio
async def test_uses_exchdisp_falling_back_to_exchange():
    search_response = {
        "quotes": [
            {
                "symbol": "A",
                "shortname": "A Corp",
                "exchDisp": "NASDAQ",
                "exchange": "NMS",
                "quoteType": "EQUITY",
            },
            {"symbol": "B", "shortname": "B Corp", "exchange": "LSE", "quoteType": "EQUITY"},
        ]
    }
    quote_response = {
        "quoteResponse": {
            "result": [
                {"symbol": "A", "currency": "USD"},
                {"symbol": "B", "currency": "GBP"},
            ]
        }
    }
    search_fetch, quote_fetch = _fetchers(search_response, quote_response)
    provider = YahooFinanceAssetSearchProvider(search_fetch=search_fetch, quote_fetch=quote_fetch)

    results = await provider.async_search("corp")
    by_symbol = {r.symbol: r.exchange for r in results}

    assert by_symbol == {"A": "NASDAQ", "B": "LSE"}


@pytest.mark.asyncio
async def test_no_search_results_returns_empty_list_without_calling_quote_fetch():
    async def should_not_be_called(url: str) -> dict:
        raise AssertionError("quote_fetch should not be called when there are no candidates")

    search_fetch, _ = _fetchers({"quotes": []}, {})
    provider = YahooFinanceAssetSearchProvider(
        search_fetch=search_fetch, quote_fetch=should_not_be_called
    )

    assert await provider.async_search("nonexistent security xyz") == []
