from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .currency_base import CurrencyProvider

FetchFn = Callable[[str], Awaitable[dict[str, Any]]]


class YahooFinanceCurrencyProvider(CurrencyProvider):
    """Sources FX rates from the same Yahoo Finance quote endpoint
    YahooFinanceProvider uses for equity prices, via currency-pair symbols
    (e.g. "USDEUR=X"). A separate class from YahooFinanceProvider per
    ADR-0002 - same underlying data source, but the two are independently
    swappable (a portfolio could use Yahoo for prices and a different
    provider for rates without either knowing about the other).
    """

    name = "yahoo_finance"

    QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"

    def __init__(self, fetch: FetchFn):
        self._fetch = fetch

    async def async_get_rates(self, base: str, targets: list[str]) -> dict[str, float]:
        # A currency converting to itself is always rate 1.0 - no API call
        # needed, and Yahoo doesn't have a "USDUSD=X" symbol to ask for.
        needed = sorted({t for t in targets if t != base})
        rates: dict[str, float] = {base: 1.0}
        if not needed:
            return rates

        # Symbol convention: "<currency><base>=X" quotes how many units of
        # `base` one unit of `currency` is worth - exactly the rate this
        # interface promises (amount_in_currency * rate = amount_in_base).
        symbol_to_currency = {f"{currency}{base}=X": currency for currency in needed}
        url = self.QUOTE_URL.format(symbols=",".join(symbol_to_currency))
        data = await self._fetch(url)

        for item in data.get("quoteResponse", {}).get("result", []):
            symbol = item.get("symbol")
            currency = symbol_to_currency.get(symbol)
            price = item.get("regularMarketPrice")
            if currency is not None and price is not None:
                rates[currency] = float(price)

        return rates
