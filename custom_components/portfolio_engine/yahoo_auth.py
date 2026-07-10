"""Cookie+crumb authentication for Yahoo Finance's quote endpoint.

Since mid-2024, `query1.finance.yahoo.com/v7/finance/quote` requires a
session cookie plus a "crumb" token; a bare request now gets a 401.

Per ADR-0002, `YahooFinanceProvider` and `YahooFinanceCurrencyProvider`
know how to *interpret* quote data, not how to authenticate an HTTP
session — that's exactly what `FetchFn` (a plain
`Callable[[str], Awaitable[dict]]`) exists to keep separate, and it's
already how `coordinator.py` decouples them from `aiohttp` itself.

So this fix lives entirely at the fetch-injection boundary: this class
produces a `fetch(url)` callable with the same signature the previous
plain closure had, but transparently attaches a valid crumb and retries
once on 401. Neither provider file changes, and neither provider's
existing unit tests (which fake `fetch` directly) are affected.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_COOKIE_URL = "https://fc.yahoo.com"
_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"

# Yahoo's crumb endpoint has been observed to reject requests with no
# User-Agent at all; this is a real browser UA string, not a spoofing
# attempt at bypassing anything Yahoo intends to gate — the quote data
# itself is the same public data the unauthenticated endpoint used to
# serve directly.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


class YahooAuthError(Exception):
    """Raised when a cookie/crumb pair cannot be obtained from Yahoo."""


class YahooCrumbFetcher:
    """Produces a `FetchFn`-compatible `fetch(url)` with crumb auth applied.

    One instance is shared between `YahooFinanceProvider` and
    `YahooFinanceCurrencyProvider` (both hit the same quote endpoint),
    so the crumb is only fetched once per coordinator, not once per
    provider.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._crumb: str | None = None

    async def _authenticate(self) -> str:
        """Fetch fresh cookies, then a crumb. Caches the crumb."""
        # Step 1: hit fc.yahoo.com so Yahoo's auth cookies land in the
        # session's cookie jar. HA's shared aiohttp session has a cookie
        # jar enabled by default, so this Just Works with the session
        # coordinator.py already passes in.
        async with self._session.get(_COOKIE_URL, headers=_HEADERS) as resp:
            await resp.read()

        # Step 2: request a crumb using those cookies.
        async with self._session.get(_CRUMB_URL, headers=_HEADERS) as resp:
            if resp.status != 200:
                raise YahooAuthError(
                    f"Failed to obtain Yahoo crumb (status {resp.status})"
                )
            crumb = (await resp.text()).strip()

        if not crumb or "<html" in crumb.lower():
            raise YahooAuthError("Yahoo returned an invalid crumb")

        self._crumb = crumb
        return crumb

    async def fetch(self, url: str) -> dict[str, Any]:
        """Fetch `url` with a valid crumb attached, JSON-decoded.

        Matches the `FetchFn` signature both Yahoo providers already
        take, so this is a drop-in replacement for the previous
        unauthenticated closure in `coordinator.py` — no other file
        needs to change.
        """
        crumb = self._crumb
        if crumb is None:
            crumb = await self._authenticate()

        authed_url = f"{url}&crumb={crumb}"
        async with self._session.get(authed_url, headers=_HEADERS) as response:
            if response.status == 401:
                # Crumb expired mid-session: re-authenticate once and
                # retry. Any failure past this point propagates up
                # unchanged, same as the old closure's raise_for_status().
                _LOGGER.debug("Yahoo crumb expired, re-authenticating once")
                crumb = await self._authenticate()
                authed_url = f"{url}&crumb={crumb}"
                async with self._session.get(
                    authed_url, headers=_HEADERS
                ) as retry_response:
                    retry_response.raise_for_status()
                    return await retry_response.json(content_type=None)

            response.raise_for_status()
            return await response.json(content_type=None)
