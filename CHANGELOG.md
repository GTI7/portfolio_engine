# Changelog

All notable changes to this project are documented here, following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

This project has **two independently-versioned components** (see ADR-0007), so each entry is tagged:

- **`[engine]`** — the HA-independent calculation core (`engine/`), versioned via `engine.__version__`.
- **`[integration]`** — the Home Assistant custom integration (`custom_components/portfolio_engine/`), versioned via `manifest.json`.
- **`[process]`** — tooling, testing infrastructure, or documentation with no version number of its own.

Entries are grouped by milestone, since that's been this project's actual release cadence so far — a dedicated `[Unreleased]` section holds anything not yet tied to a milestone.

## [Unreleased]

### Milestone 13: Dashboard & User Experience (in progress — manifest version intentionally not yet bumped)

Implementation complete and locally verified; **the integration version stays at `1.2.0`** until this milestone is fully manually validated against a real Home Assistant instance (see `docs/testing/MILESTONE_13_MANUAL_VALIDATION.md`) and ready for release — this section will be converted to a proper `integration 1.2.0 → 1.3.0` versioned entry at that point, not before.

#### Added
- `[integration]` Official dashboard package (`dashboards/portfolio_engine_dashboard.yaml`) reworked to native Home Assistant cards wherever the platform permits (`entities`, `gauge`, `history-graph`, `statistics-graph`) — markdown reserved only for the Holdings/Transactions tables (no native card renders a table from a list-valued attribute), a couple of nested-attribute summaries, and genuinely conditional/static text. Every entity ID is defined exactly once via a YAML anchor in the Overview view; every other native card references it by alias. Reorganized from 7 views into 6 (Overview, Holdings, Performance, Transactions, Analytics, Administration — merging the old Health + Import/Backup views). See ADR-0019 and `MILESTONE_13_DESIGN.md` for the full native-cards-vs-zero-config tradeoff analysis.
- `[integration]` `sensor.<portfolio>_day_change` — exposes `PerformanceCalculator`'s day-over-day change (`day_change_pct`), computed every refresh since Milestone 1 but never surfaced as an entity until now. Weighted by each position's share of total portfolio value; cash contributes 0% change. Always a concrete number, never `unknown`. Weekly/monthly/YTD change remain hardcoded `0.0` stubs in the engine itself and are deliberately not exposed as attributes here, since surfacing them would misrepresent unimplemented data as real.
- `[integration]` `sensor.<portfolio>_allocation` — exposes `AllocationCalculator`'s by-type breakdown (`group_by="type"`, computed every refresh since Milestone 3 but never surfaced until now), including the synthetic `Cash` group (ADR-0008). State is the largest group's share of total portfolio value; the full breakdown (every group's label/value/pct, already sorted largest-first) lives in the `allocation` attribute. Both new entities added minimally to the dashboard (one native row each) — no reorganization beyond that.
- ADR-0019 (dashboard stays plain Lovelace YAML; zero-config achieved via a small one-time anchor edit, not a custom frontend strategy), `MILESTONE_13_DESIGN.md`.
- Both new entities documented in `docs/ENTITY_CONTRACTS.md`, per `ENTITY_API_POLICY.md`'s "an entity isn't shipped without a contract entry" rule.

#### Fixed
- `[integration]` **`portfolio_engine.apply_import` and `portfolio_engine.create_portfolio` (both added in Milestone 12) were never deregistered when the last config entry unloads.** `tests_ha/test_apply_import_ha.py`/`test_create_portfolio_ha.py` already had tests asserting the correct deregistration behavior, written alongside each service — they simply couldn't run locally on this Windows dev environment (the known `tests_ha/` `ProactorEventLoop` limitation), so the gap went unnoticed locally until this review. Fixed in `__init__.py`'s `async_unload_entry` unload-cleanup block; no behavior change beyond the correctness fix itself.
- `[process]` `docs/ENTITY_CONTRACTS.md` was missing an entry for `sensor.<portfolio>_last_import` (added Milestone 9) — a pre-existing documentation gap against the project's own governance rule, unrelated to any code change, caught during this milestone's design review and corrected here.

#### Documentation
- `docs/user/DASHBOARDS.md` rewritten for the native-cards rework: the anchor-based configuration block, a worked before/after example, and the two new entities' minimal placements.
- `docs/testing/MILESTONE_13_MANUAL_VALIDATION.md` — the release-acceptance checklist gating this milestone's eventual version bump.
- 6 new tests: 5 pure-logic (`tests_integration/test_sensor_mapping.py` — day-change weighting, allocation grouping/sorting, empty-portfolio edge case), 1 real-HA-harness (`tests_ha/test_setup_and_entities.py` — allocation entity's full attribute shape; both new entities' state/unit also folded into that file's existing `EXPECTED_ENTITIES` table, extending its unique-id-stability and shared-device coverage to them for free) — 484 tests total (up from 478 at the previous release): 332 engine, 50 pure-logic integration, 102 real-HA-harness. (No automated coverage exists or is expected for the dashboard YAML itself — verified by a throwaway Jinja dry-run render against mocked two-portfolio data during development; real HA validation is still required before this ships, per the manual validation checklist above.)

## integration 1.1.0 → 1.2.0 / engine unchanged (1.0.0) — Milestone 12: Portfolio Import & Assisted Setup (2026-07-11)

### Added
- `[engine]` `PortfolioWriter` interface and `YamlPortfolioWriter` implementation (`repositories/writer_base.py`, `repositories/yaml_portfolio_writer.py`) — the first write path to `holdings.yaml`/`transactions.yaml` this project has ever had, deliberately kept as a separate interface from the read-only `PortfolioRepository` (ADR-0015) so every existing reader's "no side effects" guarantee stays intact and auditable. Every write goes through a single-rotation `.bak` copy + temp-file + atomic `os.replace()` sequence (ADR-0016) — no direct in-place overwrite anywhere.
- `[integration]` `portfolio_engine.apply_import` service — writes a portfolio's currently-pending `import_transactions` report's imported (non-duplicate) rows to `transactions.yaml`. All-or-nothing, no per-row selection in this version. Clears the report on success, so a second call without a fresh import fails clearly instead of double-appending. `import_transactions` itself is completely unmodified — still report-only, per its own long-standing guarantee (see ADR-0017, closing the gap `MILESTONE_9.md` flagged at the time).
- `[integration]` `portfolio_engine.create_portfolio` service — creates a brand-new portfolio (optionally pre-populated with holdings, typically assembled from prior `search_assets` calls) under an already-configured investments path. Scoped by `investments_path` rather than portfolio ID, since the target portfolio doesn't exist yet to resolve by id. Never overwrites an existing portfolio.
- `[integration]` Config Flow guided setup branch — today's `investments_path_not_found` dead end gains an opt-in path (tick "create a new portfolio here" on the same form) that creates the folder and a first portfolio inline, including a repeatable search-and-add-holding loop built on Milestone 11's `search_assets`/`YahooFinanceAssetSearchProvider`, completely unmodified. Declining leaves today's error exactly as it was. Adding a 2nd+ portfolio under an already-configured path always uses `create_portfolio` instead (ADR-0018).
- ADR-0015 (separate `PortfolioWriter` interface), ADR-0016 (atomic writes, single-rotation `.bak` backup policy — a versioned/multi-generation backup history is explicitly out of scope for now, noted as a possible future follow-up), ADR-0017 (`apply_import` as a separate, all-or-nothing service), ADR-0018 (Config Flow vs. `create_portfolio` service split).
- `MILESTONE_12_DESIGN.md`, including a Portfolio Identity Model section documenting that portfolio identity is filename-based (the directory name), never metadata (`holdings.yaml`'s own `name:` field is purely cosmetic), and the pre-existing (not introduced by this milestone) ambiguity in `_find_coordinator_for_portfolio` if two different investments paths ever contain a same-named portfolio subdirectory.
- `docs/user/PORTFOLIO_IMPORT_AND_SETUP.md`; a pointer added from `docs/user/BROKER_IMPORT.md` to it.
- 32 new tests: 11 engine unit (`tests/test_yaml_portfolio_writer.py` — atomic replace, `.bak` rotation, create/append behavior), 21 real-HA-harness (`tests_ha/test_apply_import_ha.py`, `tests_ha/test_create_portfolio_ha.py`, `tests_ha/test_config_flow_guided_setup_ha.py`) — 478 tests total (up from 449 at the previous release): 332 engine, 45 pure-logic integration, 101 real-HA-harness.

## integration 1.0.1 → 1.1.0 / engine unchanged (1.0.0) — Milestone 11: Asset Discovery (2026-07-11)

### Added
- `[engine]` `AssetSearchResult` dataclass and `AssetSearchProvider` interface (`providers/asset_search_base.py`) — a third, independent provider category alongside `PriceProvider`/`CurrencyProvider`, per ADR-0002's precedent and ADR-0014. Pure discovery: never reads or writes `holdings.yaml`/`transactions.yaml`. Deliberately lives outside `engine/models.py` — unlike `Quote`, an `AssetSearchResult` never flows into a `Portfolio`, a `Position`, or any `Calculator` (see `MILESTONE_11_DESIGN.md`).
- `[engine]` `YahooFinanceAssetSearchProvider` (`providers/yahoo_finance_asset_search.py`) — a two-call implementation: an unauthenticated call to Yahoo's public `v1/finance/search` endpoint (verified live before implementation — no crumb needed, but also no `currency` field in its response), filtered to `EQUITY`/`ETF`/`MUTUALFUND`/`CRYPTOCURRENCY` and mapped to this project's existing `stock`/`etf`/`mutual_fund`/`crypto` vocabulary, enriched with currency via one batched, crumb-authenticated call to the existing `v7/finance/quote` endpoint. See ADR-0014 for why the two calls use independently-injected fetch functions rather than one.
- `[integration]` `portfolio_engine.search_assets` service — query in, ranked candidate matches out (ticker/name/exchange/currency/type). Domain-wide, not portfolio-scoped, unlike `import_transactions`/`export_portfolio_data`. Never writes anything; an empty result list is a valid response, not an error.
- ADR-0014 — the plain-fetch-for-search / crumb-fetch-for-currency split, and why `AssetSearchResult` carries no raw Yahoo-specific fields.
- `docs/user/ASSET_DISCOVERY.md`, `MILESTONE_11_DESIGN.md`.
- 21 new tests: 12 engine unit (`tests/test_asset_search_provider.py`, fake-fetch), 3 pure-logic integration (`tests_integration/test_yahoo_asset_search_wiring.py`, proving the plain/crumb fetch split is wired correctly together), 6 real-HA-harness (`tests_ha/test_asset_search_ha.py`) — 449 tests total (up from 426 at the previous fix): 321 engine, 45 pure-logic integration, 83 real-HA-harness.

### Fixed
- `[process]` `tests/test_vendored_copy_sync.py` (new) — mechanically verifies every file in `providers/`/`engine/`/`repositories/` matches its vendored copy under `custom_components/portfolio_engine/`, modulo the one known import-path substitution. Synchronization between the two trees had been entirely manual by convention; writing this test immediately found two genuine, pre-existing drifts (a stray missing blank line in the vendored copies of `providers/yahoo_finance.py` and `repositories/yaml_repository.py`) — both fixed as part of this milestone.

### Fixed
- `[engine]` **Naive/aware datetime crash in `MwrCalculator` (via `xirr()`) for any portfolio with its first `DEPOSIT`/`WITHDRAWAL`/`TRANSFER_IN`/`TRANSFER_OUT` transaction.** `YamlRepository._parse_date()` parsed a bare date (e.g. `2024-01-10`, no time/offset component) as a naive `datetime`, while `MwrCalculator` compares transaction dates against `datetime.now(UTC)` (aware) — mixing the two raises `TypeError: can't compare offset-naive and offset-aware datetimes`, both when `xirr()` computes `t0 = min(...)` over cash flows and, more subtly, when `YamlRepository` sorts *all* of a portfolio's transactions chronologically (a single naive date among otherwise-aware ones is enough to break that sort too). Latent since Milestone 5 (MWR's introduction) — never caught because every portfolio that also happened to hit this code path in practice used full ISO timestamps with an explicit offset, and no existing test used a bare date on an external-cash-flow transaction. Fixed in `_parse_date()` (both the standalone `repositories/yaml_repository.py` and its vendored copy under `custom_components/portfolio_engine/`): a parsed date with no `tzinfo` is now given one (UTC), so every date this repository produces is consistently aware — dates that already specify a real offset are left untouched.
- 2 new tests (`tests/test_transaction_repository.py`): a bare-date transaction parses as timezone-aware, and a bare date sorts correctly alongside an explicit-offset date without raising.

## 1.0.1 (2026-07-11)

### Fixed
- `[integration]` **Yahoo Finance 401 on price/FX fetch.** `query1.finance.yahoo.com/v7/finance/quote` has required a session cookie + crumb token since mid-2024; the plain unauthenticated request `coordinator.py` built now got 401 for every user, which surfaced as the config entry stuck in `setup_retry`. Fixed at the fetch-injection boundary rather than in either provider: `coordinator.py` now wires `YahooCrumbFetcher.fetch` (new: `yahoo_auth.py`) in place of the old plain closure — same `FetchFn` signature, so `YahooFinanceProvider` and `YahooFinanceCurrencyProvider` (and their existing unit tests, which fake `fetch` directly) are untouched. Handles cookie acquisition, crumb retrieval, crumb caching across calls, and one re-authenticate-and-retry on a 401 mid-session (expired crumb). Not vendored into the standalone `engine/`/`providers/` packages — HA-only, same precedent as `store_snapshot_repository.py`.
- 4 new tests (`tests_integration/test_yahoo_auth.py`): initial auth + crumb attachment, crumb reuse across calls, one-retry-on-401 recovery, and an invalid-crumb-response error path — all against a fake session, no network or HA harness required.

### Developer
- `[process]` Fixed an import conflict in the test suite that prevented running `pytest` across `tests/` and `tests_integration/` in a single invocation — the new `test_yahoo_auth.py` above had inserted `custom_components/portfolio_engine` directly onto `sys.path`, making its vendored `providers`/`engine` packages collide with the standalone top-level ones of the same name. Fixed by importing through the same `custom_components.portfolio_engine.*` dotted path every other file in `tests_integration/` already uses, with no new `sys.path` manipulation needed.
- `[process]` Added `testpaths = tests tests_integration` to `pytest.ini` so a bare `pytest` invocation runs the full fast suite by default; `tests_ha/` remains excluded from that default and still requires its own isolated venv, unchanged. `TESTING.md` documents both the new single-invocation commands and the import convention that avoids this class of collision going forward.
- No changes to production code or Home Assistant runtime behavior.

### Added
- `[process]` This changelog.
- `[process]` `docs/ENTITY_CONTRACTS.md` — mandatory documentation template for every entity from this point forward (purpose, state meaning, unit, state class, device class, intended automation use, intended dashboard use), plus retroactive contracts for the six entities already shipped.
- `[process]` `TESTING.md` — formalizes the five independent test categories (unit, integration, performance, manual validation, compatibility validation) as the project's long-term testing structure.

## 1.0.0 — Milestone 10: Production Polish (2026-07-10)

**v1.0.0 for both the engine and the integration.** The engine's `1.0.0` is a deliberate stability declaration, not a code change — no `engine/` file was touched this milestone, continuing three consecutive milestones (8, 9, 10) of "consume the platform, don't extend it." The integration's `1.0.0` marks this as a first stable release, ready for real use.

### Added
- `[integration]` **Configuration UX fix**: `unique_id` is now the investments path itself, not a fixed domain-wide constant. The original design blocked a *second config entry from ever existing at all*, regardless of path — even though `services.py`'s coordinator lookup has supported multiple portfolios since Milestone 9. Now genuinely distinct setups are allowed; an exact duplicate path is still rejected.
- `[integration]` A **reconfigure flow** (`async_step_reconfigure`) — edit the investments path or update interval in place, without deleting and re-adding the entry (which would also mean losing the Store-backed snapshot/import history tied to the old entry_id).
- `[integration]` **`portfolio_engine.export_portfolio_data`** service — writes a complete JSON backup (holdings, full transaction history, snapshot history, last import report) for one portfolio to a path the user names explicitly. An explicit write to a *new* file the user chooses, not an automatic modification of any file this integration already owns — doesn't conflict with the import service's "no automatic writes" principle.
- `[integration]` Import quality-of-life: broker CSV files are now read with `utf-8-sig` (transparently handling the UTF-8 byte-order-mark Excel writes by default — previously a BOM'd file's header silently failed the required-column check), with a matching defensive strip inside `GenericCsvImporter` itself.
- `[integration]` `PARALLEL_UPDATES = 0` declared in `sensor.py` — the documented convention for coordinator-based entities with no per-entity I/O to throttle.
- `[process]` `docs/QUALITY_SCALE.md` — an honest, code-checked self-assessment against Home Assistant's Bronze/Silver Integration Quality Scale criteria (not a claimed certification — that requires HA-Core-review this isn't eligible for). Two real, tracked gaps identified and left open (`runtime-data` migration, icon/exception translations); `unique-config-entry` and `parallel-updates` fixed as part of writing it.
- `[process]` `hacs.json`, `LICENSE` (MIT) — HACS's structural prerequisites. `docs/RELEASE_CHECKLIST.md` — what's left to actually publish (GitHub repository, tagged releases, HACS submission), none of which is achievable without a real, public repository.
- `[process]` `docs/user/BACKUP_EXPORT.md` — end-user documentation for the export service, including a sample scheduled-backup automation.
- `[integration]` Dashboard package: two `gauge` cards (ROI, largest-position concentration) for a richer at-a-glance view within the existing core-cards-only constraint; a Backup card added to the renamed "Import / Backup" view.
- 9 new tests: 1 engine unit (BOM handling in `GenericCsvImporter`), 8 real-HA-harness (2 config-flow — multi-entry with different paths, reconfigure; 6 export-service — success, parent-directory creation, last-import inclusion, unknown-portfolio error, service deregistration) — tests genuinely exercising real HA config_entries machinery, which caught one real API mismatch before it shipped (see "Fixed" below) — 420 tests total (up from 411 at Milestone 9): 305 engine, 38 pure-logic integration (unchanged this milestone), 77 real-HA-harness.

### Fixed
- `[integration]` The reconfigure flow's first implementation called `_abort_if_unique_id_configured()` with a keyword argument (`reload_even_if_entry_is_unchanged`) that doesn't exist on this HA version's signature — a genuine API mismatch, caught immediately by the real-HA-harness test for the reconfigure flow (`TypeError`, not a passing-but-wrong test), fixed before it could ship.

### Investigated
- `[process]` `scripts/benchmark.py` numbers came back ~25–40% higher than the Milestone 9 baseline on the first re-run this milestone. Investigated rather than dismissed: confirmed stable across three runs at increasing repeat counts, zero `engine/` files touched, a uniform shift across every measurement (not concentrated at larger sizes, which a real regression would produce), and unchanged scaling ratios — pointing to environment-level load variance in this sandboxed session rather than a code regression, reported as that investigation's honest result rather than a fully conclusive claim. See `BENCHMARKS.md`'s Interpretation section.

## integration 0.3.0 / engine unchanged (0.7.0) — Milestone 9: Broker Import Framework (2026-07-10)

### Added
- `[engine]` New sibling package `importers/` (matching `repositories/`/`providers/` in shape and placement, per this milestone's own guidance to reuse the existing provider pattern) — `BrokerImportProvider` interface, `ParseResult`/`RejectedRow`, `ImportReport`/`build_import_report`, `detect_duplicates` (exact-ID plus a date+symbol+shares+amount heuristic), `deterministic_transaction_id` (for broker rows without a native reference — see ADR-0013 for why this must be deterministic, not random).
- `[engine]` Two importers: `GenericCsvImporter` (a documented, simple column schema) and `IbkrFlexQueryImporter` (Interactive Brokers Activity Flex Query XML — Trades and CashTransactions sections, verified against IBKR's own documented standard field names before implementation, not guessed).
- `[integration]` `portfolio_engine.import_transactions` service — portfolio, provider, file path in; a JSON-safe report out. Deliberately does not write to `transactions.yaml` — informational only, per the milestone's explicit scope boundary.
- `[integration]` New entity: `sensor.<portfolio>_last_import` — full contract in `docs/ENTITY_CONTRACTS.md`. Backed by `ImportReportStore` (a direct `Store` wrapper, deliberately *not* a new generic repository interface — see that module's docstring for why a single-blob persistence need doesn't warrant one).
- `[integration]` `diagnostics.py` gained a `last_import` block; dashboard package gained an Import view (last import, imported count, duplicates, errors).
- `[process]` `docs/user/BROKER_IMPORT.md` — end-user documentation for the whole import workflow, including the Generic CSV schema and IBKR Flex Query setup notes.
- 56 new tests: 44 engine unit (17 import-framework core — duplicate detection, report building, `ImportReport` serialization round-trips; 13 `GenericCsvImporter`; 11 `IbkrFlexQueryImporter`; 3 end-to-end pipeline tests proving imported transactions pass through the real, unmodified `ReconciliationCalculator`/`MwrCalculator`/`TwrCalculator`), 2 pure-logic integration (`sensor_mapping.py`'s new `get_last_import`/`get_last_import_attributes`), 10 real-HA-harness (9 broker-import service/entity/diagnostics tests, 1 new entity-polish regression test for the bug described below) — 411 tests total (up from 355 at Milestone 8).

### Fixed
- `[integration]` `PortfolioDividendIncomeSensor` (Milestone 7) combined `device_class: monetary` with `state_class: measurement` — an invalid combination `SensorDeviceClass.MONETARY` doesn't permit (only `None` or `total`). Home Assistant silently drops the invalid `state_class` at runtime rather than raising, so this had been shipping unnoticed since Milestone 7; caught via real HA-harness log output while validating Milestone 9's own new tests, unrelated to broker import itself. Fixed by unsetting `state_class` (neither `measurement` nor `total` correctly describes a rolling-12-month window) and added a regression test (`test_no_entity_has_an_invalid_device_class_state_class_combination`) covering all fifteen entities, since HA's silent-drop behavior means a passing test suite alone wouldn't catch a recurrence.

### Architecture
- `[process]` One new ADR (0013) — the maximum this milestone allowed itself. Covers the `Transaction.id`-reuse decision (no new "broker reference" field, per the milestone's own acceptance criteria) and why generated IDs must be deterministic rather than random.
- `[process]` Engine version deliberately unchanged (0.7.0) — no `engine/` file was touched; `importers/` is a sibling package that reads `engine.models.Transaction` but never modifies engine behavior, consistent with "the rest of the engine remains completely unaware of broker formats."
- `[process]` `scripts/benchmark.py` re-run and confirmed consistent with the Milestone 8 baseline within normal noise, per this milestone's own "confirm, don't assume" requirement — see `BENCHMARKS.md`'s Milestone 9 note.

## integration 0.2.0 / engine unchanged (0.7.0) — Milestone 8: Home Assistant UX & Production Readiness (2026-07-10)

An architecture-consuming milestone, not an architecture-extending one — no engine files were touched, no new ADR was needed, and every acceptance criterion the milestone set for itself (existing functionality unchanged, engine version unchanged, integration version incremented) was met exactly.

### Added
- `[integration]` **Entity polish**: every one of the fourteen entities gained an `_attr_icon` (none had one before). Reviewed and confirmed `entity_category` should stay unset (primary, not diagnostic) on all fourteen, including `portfolio_reconciliation` — documented inline in `sensor.py` as a deliberate decision, not an oversight. Unit/device-class/state-class assignments audited against `docs/ENTITY_CONTRACTS.md` and found already correct from each entity's original introduction.
- `[integration]` **Diagnostics, significantly expanded**: repository/provider identity, the active calculator registry (`{name: ClassName}` — "calculator versions" reinterpreted honestly, since calculators aren't individually versioned), engine/integration/Home Assistant Core version and minimum-supported-version, expanded snapshot statistics (oldest timestamp, span in days, alongside the existing count/latest), a new full-log transaction-statistics block (count by type, date range — distinct from the entity-facing `recent`, capped at 10), and a benchmarks reference pointing at `BENCHMARKS.md`'s own recorded engine version. Still no secrets — confirmed by a dedicated test.
- `[integration]` **Repairs framework integration** (`homeassistant.helpers.issue_registry`), four conditions, each created and cleared automatically as its condition appears/resolves on each refresh: reconciliation discrepancy, missing FX rates, snapshot repository unavailable, malformed transaction/holdings data. Issues are cleaned up on config-entry unload so a removed portfolio doesn't leave orphaned issues behind.
- `[integration]` `update_logic.py`: SnapshotRepository read/write failures now degrade gracefully (empty/unchanged snapshot list, `snapshot_repository_error` surfaced in the result) instead of failing the entire refresh — prices, positions, and every other metric keep working through a storage hiccup unrelated to market data. The coordinator surfaces this as a Repair issue rather than the integration going `unavailable`.
- `[integration]` **Official dashboard package** (`dashboards/portfolio_engine_dashboard.yaml`) — six views (Overview, Performance, Allocation, Transactions, Analytics, Health), built entirely from core Lovelace card types (`entities`/`glance`/`markdown`), no HACS dependency. Validated as genuinely correct Home Assistant configuration by submitting it to a real, separate Home Assistant instance's dashboard-storage API, confirming an exact round-trip, then removing it again — not just local YAML parsing.
- `[process]` End-user documentation (`docs/user/`): installation, getting started (portfolios/holdings/transactions/snapshots), dashboards, troubleshooting (including what every Repair issue means), FAQ — separate from the architecture-facing docs at the repository root, which remain for contributors.
- 18 new tests: 2 entity-polish regression guards (icon presence, entity-category) + 8 diagnostics-expansion tests + 5 Repairs framework tests (create/clear cycles for all four conditions, cleanup-on-unload) in `tests_ha/`, plus 3 pure-logic snapshot-repository graceful-degradation tests in `tests_integration/` — 355 tests total (up from 337 at Milestone 7): 260 engine (unchanged — no engine files touched this milestone), 36 pure-logic integration, 59 real-HA-harness.

### Changed
- `[integration]` `coordinator.py`: calculator construction split into a standalone `_build_calculators()` so the registry can be exposed for diagnostics — a coordinator-level refactor only, no engine file touched, no engine version bump.
- `[integration]` `manifest.json` version bumped 0.1.0 → 0.2.0. Engine version deliberately unchanged (0.7.0) — this milestone's own stated scope.

### Manual validation
- `MANUAL_VALIDATION_RUNBOOK.md` gained an honest execution record: what the real `pytest-homeassistant-custom-component` harness actually verified (59 tests, genuine HA Core code executing, not mocked), what the real connected HA instance's dashboard API additionally confirmed (the dashboard package's structural validity), and what remains genuinely unverified without file-write access to a real, persistent instance (Recorder statistics rendering, visual/UI screenshots, a true process-level restart, real network conditions) — recorded plainly rather than presented as complete.

## engine 0.7.0 / integration unchanged — Milestone 7: Portfolio Analytics (2026-07-09)

### Added
- `[process]` `MILESTONE_7_DESIGN.md` — a short design pass before implementation, per the milestone's own guiding principle ("the danger now isn't architecture, it's feature sprawl"). Decided which candidates become calculators, which become entities (always one per calculator, rich attributes), which become plain attributes on an existing entity (CAGR), and which are deferred (Portfolio Health, Sharpe, benchmark comparison).
- `[engine]` `engine/period_returns.py` — the cash-flow-excluded sub-period return series extracted out of `TwrCalculator`'s internals, now shared with the new `VolatilityCalculator`. Same "shared pure function, multiple calculators call it" shape `external_cash_flows.py` already established — no calculator calls another calculator.
- `[engine]` `TwrResult.annualized_pct` (CAGR) — an additive attribute on the existing TWR entity, not a new calculator or entity, fulfilling exactly what Milestone 6 deferred `twr_pct`'s annualization for.
- `[engine]` Four new calculators (eleven total): `DividendCalculator`, `DrawdownCalculator`, `VolatilityCalculator`, `PositionAnalyticsCalculator` — each independently pluggable, each producing exactly one entity with rich attributes rather than several narrow ones.
- `[integration]` Four new entities: `sensor.<portfolio>_dividend_income`, `sensor.<portfolio>_drawdown`, `sensor.<portfolio>_volatility`, `sensor.<portfolio>_concentration` — full contracts in `docs/ENTITY_CONTRACTS.md`. `coordinator.py`'s only change was registering the four new calculators; `update_logic.py` required no changes, same as Milestone 5's MWR addition.
- `[integration]` `diagnostics.py` gained `dividends`/`drawdown`/`volatility`/`concentration` blocks and `twr.annualized_pct`.
- 58 new tests: 44 engine unit (7 `period_returns.py`, 4 TWR/CAGR, 9 `DividendCalculator`, 8 `DrawdownCalculator`, 8 `VolatilityCalculator`, 8 `PositionAnalyticsCalculator`), 7 pure-logic integration, 7 real-HA-harness — 337 tests total (up from 279 at Milestone 6, of which 216 were engine, 26 pure-logic integration, 37 real-HA-harness).

### Fixed
- `[engine]` `DividendCalculator`'s first implementation filtered future-dated dividends (relative to `as_of`) out of the rolling-12-month and current-year figures, but not out of `lifetime`/`average_monthly_dividend` — found while writing `test_dividends_after_as_of_are_ignored`, before any HA-layer code existed. Fixed by filtering the whole `dividends` list to `date <= as_of` once, upfront, so every downstream figure is consistent.

### Not changed (checked, not found)
- Benchmark extended to all 11 calculators; both scaling dimensions (holdings count, snapshot-history length) remained linear/sub-linear across two independent confirming runs — unlike Milestone 6, no algorithmic issue was found this time. Recorded as a genuine negative result in `BENCHMARKS.md`, not silently skipped.

## engine 0.6.0 / integration unchanged — Milestone 6: Snapshot Engine + Time-Weighted Return (2026-07-09)

### Added
- `[engine]` `Snapshot`/`HoldingSnapshot`/`TwrResult` models, `Portfolio.snapshots` (additive field, same pattern as `transactions`). `Snapshot` carries its own `to_dict()`/`from_dict()` serialization (unlike `Transaction`) since its primary storage target is JSON-native `Store`, not a hand-edited YAML file.
- `[engine]` `SnapshotRepository` interface (`repositories/snapshot_base.py`) + `InMemorySnapshotRepository` (engine-level test double) — a new, separate repository interface from `PortfolioRepository`, since snapshots are self-generated operational data, not user/external-declared config or events. See `docs/adr/0012-snapshot-repository-and-store-backed-persistence.md`.
- `[integration]` `StoreSnapshotRepository` — the first real `Store`-backed persistence in this project (`custom_components/portfolio_engine/store_snapshot_repository.py`), fulfilling what ADR-0003 (Milestone 1) anticipated. HA-only, not vendored into the standalone engine.
- `[engine]` `engine/snapshot_policy.py` — pure `should_create_snapshot()` (once per calendar date) and `build_snapshot()` functions, matching ADR-0009's pattern of keeping policy decisions testable without HA.
- `[engine]` `engine/external_cash_flows.py` — the ADR-0011 cash-flow classification factored out of `MwrCalculator` into a shared module, now also used by `TwrCalculator`, so the two calculators can't drift apart on what counts as an external flow.
- `[engine]` `TwrCalculator` (seventh and, per the agreed roadmap, likely final calculator of this "data platform" phase — see `MILESTONE_6.md`) — links sub-period returns between consecutive `Snapshot`s (plus a synthetic final period to the live current value), excluding external cash flows from the return itself.
- `[integration]` New entity: `sensor.<portfolio>_time_weighted_return` — full contract in `docs/ENTITY_CONTRACTS.md`. `update_logic.py` gained a `snapshot_repository` parameter (its first signature change since Milestone 3) and now creates a snapshot after each successful refresh per the collection policy.
- `[integration]` `diagnostics.py` gained `snapshots` (count, latest timestamp/value, created-this-refresh) and `twr` blocks.
- 69 new tests: 56 engine unit (23 `Snapshot`/`HoldingSnapshot` model, 9 `SnapshotRepository`, 8 snapshot policy, 15 `TwrCalculator` — 13 initial + 2 added after the merge-pass rewrite, 1 benchmark-harness sanity check for the new `benchmark_snapshot_history` function), 6 pure-logic integration, 7 real-HA-harness — 279 tests total (up from 210 at Milestone 5).

### Fixed
- `[engine]` `TwrCalculator`'s original implementation re-scanned the full external-cash-flow list for every snapshot period — O(periods × flows). Harmless when flow count is small (as most engine-unit-test fixtures are), but a real risk for a portfolio with both a long snapshot history and many deposits/withdrawals over its lifetime — exactly the combination Milestone 6's own benchmark plan asked to watch for. Found by extending the benchmark to scale flow count *with* history length (the first version didn't, and hid the issue); fixed with a single sorted merge-pass over periods and flows together (O(periods + flows)). Confirmed behaviorally identical via all pre-existing hand-verified TWR tests plus two new ones (`test_flow_before_first_snapshot_is_excluded_not_attributed_to_period_0`, `test_many_flows_across_many_periods_still_correctly_attributed`). See `BENCHMARKS.md`.
- `[engine]` A genuine sign-convention bug caught during initial `TwrCalculator` test-writing (before ever reaching the integration layer): `extract_external_cash_flows`'s MWR/NPV sign convention (negative = capital into the portfolio) is the *opposite* of what TWR's `(end_value - injection)/begin_value` formula needs (a deposit must be *subtracted* from end value, requiring a positive injection figure) — using the raw MWR-convention sign produced wildly wrong returns (e.g. -45% instead of the correct -5% in one hand-verified test). Fixed before any HA-layer code was written, confirmed by the same hand-verified multi-period test suite.

## engine 0.5.0 / integration unchanged — Milestone 5: Money-Weighted Return (2026-07-09)

### Added
- `[engine]` `engine/xirr.py` — pure-numerics XIRR solver, Newton-Raphson with a bisection fallback (no numpy/scipy dependency). Validated against the canonical Excel XIRR reference example (matches to 6 decimal places) plus several hand-verifiable cases.
- `[engine]` `MwrCalculator` (sixth calculator) — builds external cash flows from `portfolio.transactions` per a specific classification (`docs/adr/0011-mwr-external-cash-flow-classification.md`): `DEPOSIT`/`WITHDRAWAL`/`TRANSFER_IN`/`TRANSFER_OUT` count, `BUY`/`SELL`/`DIVIDEND`/`FEE` don't (already reflected in the terminal portfolio value, excluding them avoids double-counting). `TRANSFER_IN`/`TRANSFER_OUT` are valued at `shares * price`, not their literal `Transaction.amount` (which is always `0.0` for transfers) — otherwise an in-kind transfer would misattribute as investment growth.
- `[engine]` `MwrResult` — three-way `status` (`"ok"` | `"no_data"` | `"insufficient_data"` | `"not_computable"`), same pattern as `ReconciliationResult`: "not computable" is a distinct claim from "computed and it's 0%."
- `[integration]` New entity: `sensor.<portfolio>_money_weighted_return` — full contract in `docs/ENTITY_CONTRACTS.md`. State is `None` (HA `unknown`) when not `"ok"`, with the reason in the `status` attribute.
- 50 new tests: 13 XIRR solver (engine unit), 11 MwrCalculator (engine unit), 3 pure-logic integration, 5 real-HA-harness — 210 tests total (up from 178 at Milestone 4) across all three automated categories.

### Fixed
- `[process]` A noisy first benchmark run (500 holdings measuring barely faster than 1000) was caught by its own implausibility and re-verified at a higher repeat count before being recorded — confirmed as sandbox CPU-contention noise, not a real regression. See `BENCHMARKS.md`.

## engine 0.4.0 / integration unchanged — Milestone 4: Transaction History (2026-07-09)

### Added
- `[engine]` `TransactionType` enum and `Transaction` dataclass (`engine/models.py`) — immutable, append-only ledger entries with an **unsigned** `amount` (direction owned entirely by `TransactionType` via `CASH_EFFECT_SIGN`, not encoded twice — revised from the original spec draft after review to remove a class of invalid data where `type` and a signed `amount` could disagree).
- `[engine]` `Portfolio.transactions` field — additive, defaults to empty; every pre-Milestone-4 `Portfolio(...)` construction continues to work unmodified.
- `[engine]` `PortfolioRepository.supports_transactions` / `.async_get_transactions()` — concrete, non-abstract methods with safe defaults (ADR-0001-consistent: no existing or hypothetical repository implementation is forced to change). `YamlRepository` implements both, reading an optional `transactions.yaml` per portfolio, with duplicate-ID detection at load time.
- `[engine]` `engine/transaction_replay.py` — `replay_transactions()` reconstructs holdings (weighted-average cost basis, matching `Holding.avg_price`'s existing method) and cash balance from a transaction log, bundled in one `TransactionReplayResult` (revised from two separate functions after review, for future extensibility). Oversold/incomplete-log positions are clamped to zero shares with a `warnings` entry rather than raising — discovered as a real edge case during implementation, not speculated in advance.
- `[engine]` `ReconciliationCalculator` and `TransactionCalculator` — two new calculators (five total), registered in the coordinator alongside the original three. `ReconciliationCalculator` compares declared state against the transaction log's reconstruction (`"ok"` / `"discrepancy"` / `"no_data"`), never treating the log as authoritative — see `docs/adr/0010-transaction-log-as-validation-layer.md`.
- `[integration]` Two new entities: `sensor.<portfolio>_transaction_count` and `sensor.<portfolio>_reconciliation` — full contracts in `docs/ENTITY_CONTRACTS.md`. `coordinator.py`'s only change was registering the two new calculators; `update_logic.py` required **zero** changes, since `portfolio.transactions` already flows through the existing, unchanged `Calculator.calculate(portfolio, positions)` interface.
- `[integration]` `diagnostics.py` gained a `reconciliation` block (troubleshooting-tier, not contract-frozen, per `ENTITY_API_POLICY.md`'s existing diagnostics carve-out).
- 178 tests total (up from 71 at Milestone 3): 136 engine unit tests, 17 pure-logic integration tests, 25 real-HA-harness tests — built in six phases (domain model → repository → replay → calculators → HA integration → documentation), each phase's tests passing before the next began, per the agreed implementation plan.

### Fixed
- `[engine]` `ReconciliationCalculator` had an O(n²) linear scan (looking up each symbol's declared `Holding` via `next(p for p in positions if ...)` inside a loop over every symbol) — found by `scripts/benchmark.py` showing super-linear scaling (2.85x time for 2x size at 500→1000 holdings), not hypothesized. Fixed with a `{symbol: Holding}` dict built once; 1000-holding benchmark time dropped from ~19.7ms to ~6.3ms, linear scaling restored. See `BENCHMARKS.md` for the full account — this is the "evolve when implementation demonstrates a genuine need" principle in action, not a pre-emptive optimization.
- `[integration]` Two new entities initially resolved to friendly name "None" (missing `translations/en.json` / `strings.json` entries for their `translation_key`s) — caught by the real-HA-harness tests, not visible in the pure-logic tests. Fixed by adding the two missing translation entries.

### Changed
- `[engine]` `MILESTONE_4_SPEC.md` was revised twice before implementation began, both times from review feedback: `Transaction.amount` changed from a signed cash-flow value to an unsigned magnitude, and `transaction_replay`'s two planned functions (`replay_holdings`/`replay_cash_balance`) were consolidated into one `replay_transactions()` returning a bundled `TransactionReplayResult`.

## engine 0.3.0 / integration unchanged — Milestone 3: Currency Support (2026-07-09)

### Added
- `[engine]` `CurrencyProvider` interface (`providers/currency_base.py`) and `YahooFinanceCurrencyProvider` (`providers/yahoo_finance_currency.py`) — separate from `PriceProvider` per ADR-0002, batches all needed currency pairs into one call, reuses the same Yahoo Finance quote endpoint via FX-pair symbols (e.g. `USDEUR=X`).
- `[engine]` `PortfolioEngine.build_positions()`/`.run()` accept an optional `fx_rates` map and convert every position to the portfolio's base currency centrally — calculators never do FX math themselves.
- `[engine]` `Position.cost_basis_base` and `Position.fx_rate` fields; `unrealized_gain`/`gain_pct` now computed on base-currency figures (numerically identical to before for same-currency portfolios — confirmed by all 31 pre-existing tests passing unmodified).
- `[integration]` Coordinator constructs and calls the currency provider; `update_logic.py` fetches rates only for currencies actually present and differing from the portfolio's base currency (a single-currency portfolio never calls it — confirmed by test).
- `[integration]` `fx_rates_missing` surfaced in the `positions` entity's attributes and in `diagnostics.py`, so a missing exchange rate is visible rather than silently approximated.
- 11 new engine tests (currency provider batching/fallback behavior, multi-currency calculator/engine runs), 3 new pure-logic integration tests, 2 new real-HA-harness tests (multi-currency setup, missing-rate fallback) — 71 tests total across all three automated categories.

### Changed
- `[engine]` Missing FX rate falls back to 1.0 (documented best-effort, not a crash) — same-currency-only accuracy limitation from Milestones 1–2 is now resolved for currencies the provider successfully returns a rate for.

## Milestone 2.5 — Validation (2026-07-09)

### Added
- `[integration]` 18 automated tests (`tests_ha/`) against the real `pytest-homeassistant-custom-component` harness — real `ConfigFlow`, `OptionsFlow`, `DataUpdateCoordinator`, `SensorEntity`, `diagnostics.py`, not mocks of them.
- `[process]` `scripts/setup_ha_test_env.sh`, `requirements-ha-test.txt` — isolated venv setup for the HA test harness, kept separate from the fast unit-test path.
- `[process]` `docs/COMPATIBILITY_POLICY.md` — minimum supported HA version (2025.1, set from what `tests_ha/` actually validates), compatibility/deprecation policy, release-notes requirement for breaking changes.
- `[process]` `docs/ENTITY_API_POLICY.md` — operationalizes ADR-0006 into concrete per-entity rules.
- `[process]` `MANUAL_VALIDATION_RUNBOOK.md` — checklist for Recorder statistics, restart persistence, and real-network failure recovery; explicitly not yet executed against a live instance.

### Fixed
- `[process]` (test infrastructure only, no product code changed) Test teardown leaking a background thread from an unused real `aiohttp.ClientSession` construction — tests now mock `async_get_clientsession` alongside the provider call.

## Milestone 2 — Home Assistant Integration (2026-07-09)

### Added
- `[integration]` Initial release: `ConfigFlow` + `OptionsFlow`, `DataUpdateCoordinator`, clean setup/unload/reload lifecycle, `diagnostics.py`.
- `[integration]` Six public entities (see ADR-0006, `docs/ENTITY_API_POLICY.md`): `portfolio_value`, `portfolio_total_invested`, `portfolio_total_profit`, `portfolio_roi`, `portfolio_cash_balance`, `portfolio_positions`.
- `[integration]` `update_logic.py` / `sensor_mapping.py` — HA-independent pure-logic modules backing the coordinator and sensors (ADR-0009), covered by 9 tests (`tests_integration/`) at release time.
- `[process]` `custom_components/portfolio_engine/engine|repositories|providers/` — vendored copies of the engine package for self-contained integration packaging.

### Changed
- `[engine]` **Breaking (pre-1.0, no external consumers):** `Calculator.calculate()` signature changed from `(positions, base_currency)` to `(portfolio, positions)` to support first-class cash accounting (see next entry, ADR-0008).

## engine 0.2.0 — Cash as a First-Class Concept (2026-07-09)

### Added
- `[engine]` `Portfolio.cash_balance` field (validated non-negative).
- `[engine]` `PortfolioSummary.total_positions_value`, `.cash_balance`, and `.total_value` (positions + cash) — `.total_invested`/`.roi_pct` remain invested-capital-only.
- `[engine]` `AllocationCalculator` now emits a `"Cash"` group whenever `cash_balance > 0`, so allocation percentages sum to 100 including cash.
- `[engine]` `PerformanceCalculator` includes cash in the weighting denominator (implicit 0% contribution).
- 8 new tests covering cash-inclusive behavior across all three calculators and one end-to-end engine run.

### Changed
- `[engine]` See `Calculator.calculate()` signature change above (ADR-0008) — this is the change that introduced it.

## engine 0.1.0 — Milestone 1: Foundation (2026-07-08)

### Added
- `[engine]` Initial domain model (`Quote`, `Holding`, `Position`, `Portfolio`, and calculator result types) and three calculators: `PortfolioCalculator`, `AllocationCalculator`, `PerformanceCalculator` (ADR-0004: deliberately minimal set, not a full stub-everything scaffold).
- `[engine]` `PortfolioRepository` / `YamlRepository` (ADR-0001) and `PriceProvider` / `YahooFinanceProvider` (ADR-0002) — I/O and calculation kept strictly separate.
- `[process]` 20 initial tests, `docs/adr/0001`–`0005`.
- `[process]` (Milestone 1 addendum, same date) `mypy --strict`, `ruff` + pre-commit, `scripts/benchmark.py` with a recorded 100/500/1000-holding baseline (`BENCHMARKS.md`), independent engine semantic versioning (ADR-0007), and `ADR-0006` (public entity stability, written ahead of Milestone 2 shipping any entities).
