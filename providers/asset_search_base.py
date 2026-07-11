"""Asset search provider interface - supplies discovery results ONLY.

Per ADR-0002's precedent (each provider category gets its own small ABC,
no inheritance with sibling interfaces) and ADR-0014: asset discovery
answers "what instruments could this query mean," a third, independent
question from PriceProvider ("what is this instrument worth") and
CurrencyProvider ("how do two currencies compare"). Never modifies
portfolio files - pure discovery, no I/O side effects on holdings.yaml/
transactions.yaml.

AssetSearchResult lives here, not in engine/models.py, deliberately -
unlike Quote (consumed by build_positions and every calculator,
independent of which provider produced it), an AssetSearchResult is
produced and consumed entirely at the discovery/service boundary and
never flows into a Portfolio, a Position, or any Calculator. Its
placement follows the same core-engine-vs-sibling-capability boundary
that keeps engine.__version__ unbumped by this feature (see ADR-0014
and MILESTONE_11_DESIGN.md).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AssetSearchResult:
    """One candidate match from an AssetSearchProvider - discovery output,
    never persisted, never a Holding. `asset_type` deliberately reuses
    Holding.type's free-string convention (no enum exists anywhere in this
    codebase for this) so a discovery result's type can be dropped straight
    into a holdings.yaml `type:` field without any translation step.

    Deliberately provider-agnostic: no raw provider-specific fields
    (e.g. Yahoo's `quoteType`/raw exchange code) are carried here - see
    ADR-0014. A concrete provider that needs to expose its own raw data
    for debugging should log it, not smuggle it through this shape.
    """

    symbol: str
    name: str
    exchange: str
    currency: str
    asset_type: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("AssetSearchResult: symbol is required")
        if not self.exchange:
            raise ValueError(f"{self.symbol}: exchange is required")
        if not self.currency:
            raise ValueError(f"{self.symbol}: currency is required")
        if not self.asset_type:
            raise ValueError(f"{self.symbol}: asset_type is required")


class AssetSearchProvider(ABC):
    @abstractmethod
    async def async_search(self, query: str, limit: int = 10) -> list[AssetSearchResult]:
        """Return up to `limit` matches for a free-text query, ranked by
        relevance (provider-defined order - callers should not assume a
        particular sort key beyond "best match first"). An empty query or
        a non-positive limit should short-circuit without a network call,
        matching PriceProvider/CurrencyProvider's empty-input convention.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
