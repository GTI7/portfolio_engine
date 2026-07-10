"""Tests for YahooCrumbFetcher (v1.0.1 fix for the Yahoo 401).

Lives in tests_integration/ (not tests/) since it exercises
custom_components/portfolio_engine/yahoo_auth.py, an HA-integration-only
file not vendored into the standalone engine package - same reasoning
as store_snapshot_repository.py.

Uses a fake, duck-typed session instead of a real aiohttp.ClientSession
or a real HA harness: this class only ever calls `session.get(url,
headers=...)` as an async context manager, so a minimal fake is enough
to test its cookie/crumb/retry logic in isolation, without either a
network call or the heavier tests_ha/ harness.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components" / "portfolio_engine"))

from yahoo_auth import YahooAuthError, YahooCrumbFetcher  # noqa: E402


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
    """Scripted responses per-URL-prefix; records every call made."""

    def __init__(self, responses: dict[str, list[FakeResponse]]):
        self._responses = responses
        self.calls: list[str] = []

    def get(self, url: str, headers=None):
        self.calls.append(url)
        for prefix, queue in self._responses.items():
            if url.startswith(prefix):
                return queue.pop(0) if len(queue) > 1 else queue[0]
        raise AssertionError(f"Unexpected URL: {url}")


QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=AAPL"


@pytest.mark.asyncio
async def test_authenticates_then_fetches_with_crumb():
    session = FakeSession(
        {
            "https://fc.yahoo.com": [FakeResponse(status=200)],
            "https://query1.finance.yahoo.com/v1/test/getcrumb": [
                FakeResponse(status=200, text="abc123crumb")
            ],
            QUOTE_URL: [FakeResponse(status=200, json_body={"quoteResponse": {"result": []}})],
        }
    )
    fetcher = YahooCrumbFetcher(session)

    result = await fetcher.fetch(QUOTE_URL)

    assert result == {"quoteResponse": {"result": []}}
    # crumb was appended to the actual quote request
    assert any("crumb=abc123crumb" in call for call in session.calls if "v7/finance" in call)


@pytest.mark.asyncio
async def test_reuses_cached_crumb_across_calls():
    session = FakeSession(
        {
            "https://fc.yahoo.com": [FakeResponse(status=200)],
            "https://query1.finance.yahoo.com/v1/test/getcrumb": [
                FakeResponse(status=200, text="cached-crumb")
            ],
            QUOTE_URL: [FakeResponse(status=200, json_body={"quoteResponse": {"result": []}})],
        }
    )
    fetcher = YahooCrumbFetcher(session)

    await fetcher.fetch(QUOTE_URL)
    await fetcher.fetch(QUOTE_URL)

    crumb_calls = [c for c in session.calls if "getcrumb" in c]
    assert len(crumb_calls) == 1  # not re-fetched on the second call


@pytest.mark.asyncio
async def test_401_triggers_one_reauth_and_retry():
    call_count = {"quote": 0}

    class OneTimeFailSession(FakeSession):
        def get(self, url, headers=None):
            self.calls.append(url)
            if "fc.yahoo.com" in url:
                return FakeResponse(status=200)
            if "getcrumb" in url:
                return FakeResponse(status=200, text="crumb1" if call_count["quote"] == 0 else "crumb2")
            if "v7/finance" in url:
                call_count["quote"] += 1
                if call_count["quote"] == 1:
                    return FakeResponse(status=401)
                return FakeResponse(status=200, json_body={"quoteResponse": {"result": []}})
            raise AssertionError(url)

    session = OneTimeFailSession({})
    fetcher = YahooCrumbFetcher(session)

    result = await fetcher.fetch(QUOTE_URL)

    assert result == {"quoteResponse": {"result": []}}
    assert call_count["quote"] == 2  # first 401, then a successful retry


@pytest.mark.asyncio
async def test_invalid_crumb_response_raises_auth_error():
    session = FakeSession(
        {
            "https://fc.yahoo.com": [FakeResponse(status=200)],
            "https://query1.finance.yahoo.com/v1/test/getcrumb": [
                FakeResponse(status=200, text="<html>not a crumb</html>")
            ],
        }
    )
    fetcher = YahooCrumbFetcher(session)

    with pytest.raises(YahooAuthError):
        await fetcher.fetch(QUOTE_URL)
