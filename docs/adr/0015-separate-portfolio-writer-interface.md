# ADR 0015: Portfolio Writes Go Through a New `PortfolioWriter` Interface, Not `PortfolioRepository`

**Status:** Accepted
**Date:** 2026-07-11

## Decision

Introduce a new, separate abstract interface, `PortfolioWriter` (`repositories/writer_base.py`), and its concrete implementation `YamlPortfolioWriter` (`repositories/yaml_portfolio_writer.py`) — both mirrored under `custom_components/portfolio_engine/repositories/` per the existing vendoring convention. `PortfolioRepository`/`YamlRepository` gain **no new methods**; every write this milestone introduces (creating a portfolio, appending transactions) goes through `PortfolioWriter` instead.

## Reason

`PortfolioRepository`'s own docstring states its contract plainly: "repositories never calculate portfolio metrics... returns raw `Holding`/`Portfolio` objects exactly as configured." Every existing caller of `async_get_portfolios()`/`async_get_transactions()` — the coordinator's every refresh cycle, every calculator indirectly, `export_portfolio_data` — currently depends on that method never having a write side effect, and that invariant is trivially auditable today by the simple fact that grepping `yaml_repository.py` for `.write_text(` returns nothing. Milestone 12 is the first milestone to ever write to `holdings.yaml`/`transactions.yaml` programmatically; bolting that capability onto the class every read path already depends on would mean every future reader of `YamlRepository`'s source has to reason about whether a given method might mutate the file it's reading, forever, for a capability only two new services and one config-flow branch actually use.

This follows the exact same "different questions get different interfaces" precedent ADR-0002 established for `PriceProvider`/`CurrencyProvider` and MILESTONE_11_DESIGN.md reapplied for `AssetSearchProvider` ("a third, independent question... per ADR-0002's precedent"). Reading a portfolio and mutating its backing files are two different questions in the same sense; giving them a fourth, separate interface is consistent with — not an exception to — how this codebase has drawn every prior capability boundary.

## Alternatives Considered

- **Add `async_create_portfolio`/`async_append_transactions` directly to `PortfolioRepository`/`YamlRepository`.** Rejected — every implementation of `PortfolioRepository` (hypothetical future non-YAML ones included) would either have to implement writes or accept default no-op/raising stubs for a capability not every repository necessarily should support (a read-only broker-API-backed repository, for instance, has no sensible "write" story at all). Keeping writes on a separate, opt-in interface means a repository that's read-only by nature simply never implements `PortfolioWriter` — no stub methods, no `NotImplementedError` surprises.
- **A single `YamlPortfolioWriter` with no ABC**, since there is (for now) exactly one concrete implementation. Rejected for the same reason `PriceProvider`/`CurrencyProvider`/`AssetSearchProvider` all have ABCs despite each having exactly one concrete implementation today — the interface is what makes the write path fakeable in unit tests without real file I/O, and it documents the contract independent of the one implementation that happens to exist.
- **Merge writer and reader into one `YamlPortfolioStore` class that implements both interfaces.** Considered — would save duplicating the `base_path / portfolio_id / "holdings.yaml"` path-join convention across two files. Rejected: the duplication is genuinely trivial (a handful of near-identical lines, not real shared logic), and a single class satisfying two interfaces reintroduces exactly the "does this class have side effects" ambiguity this ADR exists to avoid — anyone holding a reference to it can no longer assume from its type alone whether it's read-only.

## Consequences

- The coordinator (`coordinator.py`) continues to hold only a `PortfolioRepository` — nothing about its existing refresh logic needs re-auditing for write safety, and it never constructs or touches a `PortfolioWriter`.
- The two new services (`apply_import`, `create_portfolio`) and the Config Flow's new guided branch (ADR-0018) each construct their own `YamlPortfolioWriter(base_path)` directly, the same "construct fresh, no factory/registry" pattern `_async_search_assets` already established for `YahooFinanceAssetSearchProvider`.
- A future non-YAML `PortfolioRepository` (still hypothetical, none exists) can remain entirely read-only without implementing anything write-related.
- `repositories/` now has two small, sibling ABCs instead of one — matches this project's now-repeated pattern of narrow, single-purpose interfaces over fewer, broader ones.
