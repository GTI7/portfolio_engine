# ADR 0014: Asset Search Uses an Unauthenticated Fetch for Yahoo's Search Endpoint, Reserving `YahooCrumbFetcher` for Currency Enrichment Only

**Status:** Accepted
**Date:** 2026-07-11

## Decision

`YahooFinanceAssetSearchProvider` takes two independently-injected `FetchFn`s — `search_fetch` (a plain, unauthenticated GET+JSON) for Yahoo's `v1/finance/search` endpoint, and `quote_fetch` (bound to a `YahooCrumbFetcher` instance's `.fetch`) for the `v7/finance/quote` currency-enrichment call. The provider itself never constructs its own HTTP session or auth mechanism, matching the injection-point convention `YahooFinanceProvider`/`YahooFinanceCurrencyProvider` already use.

Also per this decision: `AssetSearchResult` carries no raw Yahoo-specific fields (no raw `quoteType`, no raw exchange code) — see "Alternatives Considered" below for why that's part of the same reasoning, not a separate choice.

## Reason

Live verification against the real endpoint (no crumb/cookie sent) confirmed `v1/finance/search` is fully public and returns complete results with no auth. It also confirmed the search response carries no `currency` field at all — that has to come from a second call to `v7/finance/quote`, which *does* require the crumb per the v1.0.1 fix (`YahooCrumbFetcher`, `yahoo_auth.py`). Attaching a crumb to the search call would be attaching auth to a call that provably doesn't need it — not a decision grounded in anything the API actually requires, and it would make the search leg needlessly depend on crumb authentication succeeding even though the search endpoint itself never asked for it.

## Alternatives Considered

- **Reuse `YahooCrumbFetcher.fetch` unconditionally for both calls** — rejected. Appending an unused `&crumb=` parameter to a public endpoint would likely be harmlessly ignored, but that's an unverified assumption about Yahoo's server-side behavior, not a design decision — and it would make the search leg fail if crumb authentication is ever unavailable (e.g. Yahoo changes `fc.yahoo.com`/`getcrumb` again), for a call that has no actual dependency on that mechanism.
- **A single provider-owned `aiohttp.ClientSession`, bypassing the `FetchFn` injection pattern entirely** — rejected. Breaks the exact unit-testability property every existing provider's own docstring and test file rely on (`FetchFn` injection is what lets these be tested with a fake fetcher, no real HTTP client).
- **A single unified `FetchFn` that internally decides whether to attach a crumb based on the URL it's given** — rejected as needless indirection. The provider already knows, at each call site, which of its two calls needs auth; encoding that as "the fetch function inspects its own URL argument" hides a decision the provider already has for free, and makes each fetch function harder to test in isolation.
- **Carry Yahoo's raw `quoteType` and raw exchange code on `AssetSearchResult`, for future debugging** — rejected. Every existing provider-boundary dataclass in this codebase (`Quote`, `Holding`) is already a clean, provider-agnostic abstraction; `AssetSearchProvider`'s whole point (per ADR-0002's "different questions" framing, applied a third time) is to answer "what could this query mean" independent of which concrete provider answered it. Baking Yahoo-specific vocabulary into the return type would mean a hypothetical future non-Yahoo provider either can't populate those fields meaningfully or has to fake Yahoo's vocabulary just to satisfy the shape. The actual debugging need is met by `_LOGGER.debug(...)`-ing the raw search and quote-enrichment responses inside `YahooFinanceAssetSearchProvider` instead — the same observability mechanism `yahoo_auth.py` already established, without polluting the contract every caller (current and future) depends on.

## Consequences

- A new HA service (`portfolio_engine.search_assets`) constructs its own `YahooCrumbFetcher(async_get_clientsession(hass))` independently of `coordinator.py`'s instance — this re-authenticates/caches its own crumb per service call rather than sharing a coordinator's cached crumb. Acceptable: `YahooCrumbFetcher` is cheap to construct, and its crumb-cache lifetime is already documented as per-instance, not global.
- Any future provider that needs both an authenticated and unauthenticated Yahoo call follows the same two-`FetchFn` injection shape this ADR establishes, rather than re-deciding it.
- Slightly more constructor plumbing in `services.py` (two fetch closures instead of one) — judged acceptable given it keeps auth attached only where it's actually required.
- `AssetSearchResult` stays genuinely provider-agnostic; a future non-Yahoo `AssetSearchProvider` implementation can populate it fully without needing to invent placeholder values for fields it has no equivalent of.
