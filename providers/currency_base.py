"""Exchange-rate provider interface - supplies FX rates ONLY.

Per ADR-0002, this is deliberately a separate interface from PriceProvider,
even though a single provider (Yahoo Finance) can implement both under the
hood: prices answer "what is this instrument worth," rates answer "how do
two currencies compare," and a portfolio can reasonably want independent
sources for each (e.g. equity prices from one provider, a dedicated FX rate
feed from another) without the two being coupled.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class CurrencyProvider(ABC):
    @abstractmethod
    async def async_get_rates(self, base: str, targets: list[str]) -> dict[str, float]:
        """Return a currency -> rate map, where multiplying an amount
        denominated in that currency by its rate converts it into `base`
        (i.e. `amount_in_base = amount_in_currency * rates[currency]`).

        `base` itself is not required to appear in the returned mapping
        (its rate would trivially be 1.0 - callers should treat a missing
        entry for `base` as 1.0 rather than require providers to special-
        case it). Should batch internally where the underlying API
        supports it, matching PriceProvider's convention.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
