"""Yahoo Finance-backed AssetSearchProvider - see ADR-0014 for the two-call
design (a plain, unauthenticated call to the public search endpoint, then
one batched, crumb-authenticated call to the existing quote endpoint for
currency enrichment - search results carry no currency field at all,
verified against the live endpoint before writing this).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .asset_search_base import AssetSearchProvider, AssetSearchResult

_LOGGER = logging.getLogger(__name__)

# A fetch function's signature: given a URL, return parsed JSON. Same
# injection shape every other Yahoo-backed provider uses (see
# yahoo_finance.py / yahoo_finance_currency.py) - two are injected here
# rather than one, since the two calls this provider makes have genuinely
# different auth requirements (see ADR-0014).
FetchFn = Callable[[str], Awaitable[dict[str, Any]]]

#: Yahoo `quoteType` -> this project's informal Holding.type vocabulary
#: (see engine/models.py's Holding - a free string, no enum). A closed,
#: explicit map, not a passthrough of whatever string Yahoo happens to
#: send - anything not a key here (INDEX, FUTURE, OPTION, CURRENCY, ...)
#: is filtered out of results entirely, since this project's holdings.yaml
#: vocabulary has no home for them yet.
_QUOTE_TYPE_MAP: dict[str, str] = {
    "EQUITY": "stock",
    "ETF": "etf",
    "MUTUALFUND": "mutual_fund",
    "CRYPTOCURRENCY": "crypto",
}


class YahooFinanceAssetSearchProvider(AssetSearchProvider):
    name = "yahoo_finance"

    SEARCH_URL = (
        "https://query1.finance.yahoo.com/v1/finance/search"
        "?q={query}&quotesCount={limit}&newsCount=0"
    )
    QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"

    def __init__(self, search_fetch: FetchFn, quote_fetch: FetchFn):
        self._search_fetch = search_fetch
        self._quote_fetch = quote_fetch

    async def async_search(self, query: str, limit: int = 10) -> list[AssetSearchResult]:
        if not query or limit <= 0:
            return []

        search_url = self.SEARCH_URL.format(query=query, limit=limit)
        search_data = await self._search_fetch(search_url)
        _LOGGER.debug("Yahoo asset search raw response for %r: %s", query, search_data)

        candidates: list[dict[str, Any]] = []
        for quote in search_data.get("quotes", []):
            symbol = quote.get("symbol")
            asset_type = _QUOTE_TYPE_MAP.get(quote.get("quoteType"))
            if not symbol or asset_type is None:
                # Missing symbol, or a quoteType this project doesn't
                # support yet (INDEX/FUTURE/OPTION/...) - filtered, not an
                # error; this is expected, routine input, not malformed data.
                continue
            candidates.append(
                {
                    "symbol": symbol,
                    "name": quote.get("longname") or quote.get("shortname") or symbol,
                    "exchange": quote.get("exchDisp") or quote.get("exchange") or "",
                    "asset_type": asset_type,
                }
            )

        if not candidates:
            return []

        # Batch currency-enrich in one call - same batching discipline as
        # YahooFinanceCurrencyProvider/YahooFinanceProvider: N candidates
        # still costs one HTTP round trip, not N.
        symbols = [c["symbol"] for c in candidates]
        quote_url = self.QUOTE_URL.format(symbols=",".join(symbols))
        quote_data = await self._quote_fetch(quote_url)
        _LOGGER.debug("Yahoo quote enrichment raw response for %s: %s", symbols, quote_data)

        currency_by_symbol: dict[str, str] = {
            item["symbol"]: item["currency"]
            for item in quote_data.get("quoteResponse", {}).get("result", [])
            if item.get("symbol") and item.get("currency")
        }

        results: list[AssetSearchResult] = []
        for candidate in candidates:
            currency = currency_by_symbol.get(candidate["symbol"])
            if not currency:
                # No currency available for this symbol in the enrichment
                # response - dropped rather than returned with a placeholder,
                # matching the existing "malformed/missing item is silently
                # skipped, not raised" convention (see
                # YahooFinanceCurrencyProvider's missing-rate handling).
                continue
            results.append(
                AssetSearchResult(
                    symbol=candidate["symbol"],
                    name=candidate["name"],
                    exchange=candidate["exchange"],
                    currency=currency,
                    asset_type=candidate["asset_type"],
                )
            )
        return results
