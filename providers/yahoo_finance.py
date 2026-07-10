from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from engine.models import Quote

from .price_base import PriceProvider

# A fetch function's signature: given a URL, return parsed JSON.
# Injected rather than hard-coding aiohttp here so this provider is
# unit-testable with a fake fetcher and swappable for HA's shared
# aiohttp_client session without changing this class.
FetchFn = Callable[[str], Awaitable[dict[str, Any]]]


class YahooFinanceProvider(PriceProvider):
    name = "yahoo_finance"

    QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"

    def __init__(self, fetch: FetchFn):
        self._fetch = fetch

    async def async_get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        if not symbols:
            return {}

        # One batched call for all symbols — this is the scalability
        # property discussed in the architecture doc Section 6: N holdings
        # still costs one HTTP round trip, not N.
        url = self.QUOTE_URL.format(symbols=",".join(symbols))
        data: dict[str, Any] = await self._fetch(url)

        results: dict[str, Quote] = {}
        for item in data.get("quoteResponse", {}).get("result", []):
            symbol = item.get("symbol")
            if not symbol:
                continue
            results[symbol] = Quote(
                symbol=symbol,
                price=float(item.get("regularMarketPrice", 0.0)),
                currency=item.get("currency", "USD"),
                change_pct=float(item.get("regularMarketChangePercent", 0.0)),
                name=item.get("longName") or item.get("shortName"),
                as_of=datetime.now(UTC),
            )
        return results
