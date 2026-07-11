"""Proves the plain-fetch-for-search / crumb-fetch-for-currency split
(ADR-0014) is wired correctly when both real fetch mechanisms interact
together - the one thing tests/test_asset_search_provider.py's fake-FetchFn
unit tests can't observe (they fake both fetch functions directly, so
neither ever touches real crumb/session mechanics), and the one thing
tests_integration/test_yahoo_auth.py's YahooCrumbFetcher-only tests don't
cover either (they never touch the search endpoint).

Uses the same fake, duck-typed session pattern as test_yahoo_auth.py -
no real network call, no real HA harness.
"""

from __future__ import annotations

import pytest

from custom_components.portfolio_engine.providers.yahoo_finance_asset_search import (
    YahooFinanceAssetSearchProvider,
)
from custom_components.portfolio_engine.yahoo_auth import YahooCrumbFetcher

SEARCH_RESPONSE = {
    "quotes": [
        {
            "symbol": "VWCE.DE",
            "longname": "Vanguard FTSE All-World UCITS ETF",
            "exchDisp": "XETRA",
            "quoteType": "ETF",
        }
    ]
}
QUOTE_RESPONSE = {"quoteResponse": {"result": [{"symbol": "VWCE.DE", "currency": "EUR"}]}}


class FakeResponse:
    def __init__(self, status: int = 200, text: str = "", json_body: dict | None = None):
        self.status = status
        self._text = text
        self._json_body = json_body if json_body is not None else {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read(self):
        return b""

    async def text(self):
        return self._text

    async def json(self, content_type=None):
        return self._json_body

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


class FakeSession:
    """Scripted responses per-URL-prefix; records every call made,
    including whether `headers` was passed (YahooCrumbFetcher always
    passes headers; a plain fetch doesn't need to).
    """

    def __init__(self, responses: dict[str, FakeResponse]):
        self._responses = responses
        self.calls: list[str] = []

    def get(self, url: str, headers=None):
        self.calls.append(url)
        for prefix, response in self._responses.items():
            if url.startswith(prefix):
                return response
        raise AssertionError(f"Unexpected URL: {url}")


async def _plain_fetch(session: FakeSession, url: str) -> dict:
    """Mirrors the plain, unauthenticated fetch services.py builds for the
    search leg - no crumb, no cookie dance, just GET + JSON.
    """
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


@pytest.mark.asyncio
async def test_search_call_carries_no_crumb_parameter():
    session = FakeSession(
        {
            "https://query1.finance.yahoo.com/v1/finance/search": FakeResponse(
                status=200, json_body=SEARCH_RESPONSE
            ),
            "https://fc.yahoo.com": FakeResponse(status=200),
            "https://query1.finance.yahoo.com/v1/test/getcrumb": FakeResponse(
                status=200, text="abc123crumb"
            ),
            "https://query1.finance.yahoo.com/v7/finance/quote": FakeResponse(
                status=200, json_body=QUOTE_RESPONSE
            ),
        }
    )
    crumb_fetcher = YahooCrumbFetcher(session)

    async def search_fetch(url: str) -> dict:
        return await _plain_fetch(session, url)

    provider = YahooFinanceAssetSearchProvider(
        search_fetch=search_fetch, quote_fetch=crumb_fetcher.fetch
    )

    await provider.async_search("Vanguard FTSE All-World")

    search_calls = [c for c in session.calls if "v1/finance/search" in c]
    assert len(search_calls) == 1
    assert "crumb=" not in search_calls[0]


@pytest.mark.asyncio
async def test_quote_enrichment_call_does_carry_a_crumb():
    session = FakeSession(
        {
            "https://query1.finance.yahoo.com/v1/finance/search": FakeResponse(
                status=200, json_body=SEARCH_RESPONSE
            ),
            "https://fc.yahoo.com": FakeResponse(status=200),
            "https://query1.finance.yahoo.com/v1/test/getcrumb": FakeResponse(
                status=200, text="abc123crumb"
            ),
            "https://query1.finance.yahoo.com/v7/finance/quote": FakeResponse(
                status=200, json_body=QUOTE_RESPONSE
            ),
        }
    )
    crumb_fetcher = YahooCrumbFetcher(session)

    async def search_fetch(url: str) -> dict:
        return await _plain_fetch(session, url)

    provider = YahooFinanceAssetSearchProvider(
        search_fetch=search_fetch, quote_fetch=crumb_fetcher.fetch
    )

    await provider.async_search("Vanguard FTSE All-World")

    quote_calls = [c for c in session.calls if "v7/finance/quote" in c]
    assert len(quote_calls) == 1
    assert "crumb=abc123crumb" in quote_calls[0]


@pytest.mark.asyncio
async def test_crumb_is_fetched_once_even_though_only_the_second_leg_needs_it():
    session = FakeSession(
        {
            "https://query1.finance.yahoo.com/v1/finance/search": FakeResponse(
                status=200, json_body=SEARCH_RESPONSE
            ),
            "https://fc.yahoo.com": FakeResponse(status=200),
            "https://query1.finance.yahoo.com/v1/test/getcrumb": FakeResponse(
                status=200, text="abc123crumb"
            ),
            "https://query1.finance.yahoo.com/v7/finance/quote": FakeResponse(
                status=200, json_body=QUOTE_RESPONSE
            ),
        }
    )
    crumb_fetcher = YahooCrumbFetcher(session)

    async def search_fetch(url: str) -> dict:
        return await _plain_fetch(session, url)

    provider = YahooFinanceAssetSearchProvider(
        search_fetch=search_fetch, quote_fetch=crumb_fetcher.fetch
    )

    await provider.async_search("Vanguard FTSE All-World")

    crumb_calls = [c for c in session.calls if "getcrumb" in c]
    assert len(crumb_calls) == 1
