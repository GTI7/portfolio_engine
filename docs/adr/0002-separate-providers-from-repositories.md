# ADR 0002: Separate Market Data Providers from Portfolio Repositories

**Status:** Accepted
**Date:** 2026-07-09

## Decision

`PriceProvider` (market data: quotes, FX rates) and `PortfolioRepository` (portfolio data: holdings, transactions) are distinct interfaces with no inheritance relationship between them. A class may implement both (e.g. a future broker integration), but the interfaces themselves stay separate.

## Reason

These answer different questions: "what is this instrument worth right now" versus "what do I own." Conflating them into one interface would force every provider to implement portfolio-storage methods it doesn't need (Yahoo Finance has no concept of "my holdings") and every repository to implement pricing methods it doesn't need (a plain YAML file has no concept of "current AAPL price").

## Alternatives Considered

- **Single `DataSource` interface covering both** — rejected; would require every implementation to stub out half the interface, and blurs a distinction (market data vs. personal data) that matters for security/scope (a broker credential should not be required just to fetch a public stock price, and vice versa).
- **Provider supplies both prices and holdings for broker integrations** — accepted as a *composition*, not a merged interface: a broker class can implement both `PriceProvider` and `PortfolioRepository` and be registered as both, while the two contracts remain independently testable and independently swappable.

## Consequences

- A user can mix and match freely: YAML holdings + Yahoo Finance prices, or broker-synced holdings + a different pricing source, without either side knowing about the other's implementation.
- Slightly more boilerplate for a broker integration (implement two interfaces instead of one), which is judged acceptable given how few broker integrations exist versus how many holdings-only setups do.
