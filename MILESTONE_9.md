# Milestone 9: Broker Import Framework (Read-Only)

**Status:** Complete for the exact scope in the brief. Two importers, one service, one entity, one ADR (the maximum allowed), zero engine changes.

## What's included

- **`importers/`** — a new sibling package to `repositories/`/`providers/`, same shape: `BrokerImportProvider` interface, two concrete implementations, and pure supporting logic (`duplicate_detection.py`, `report.py`, `id_generation.py`) that never touches Home Assistant.
- **`GenericCsvImporter`** — a documented, simple CSV schema for brokers without a dedicated importer.
- **`IbkrFlexQueryImporter`** — Interactive Brokers Activity Flex Query XML (Trades + CashTransactions sections), built against IBKR's own documented standard field names, verified by web search before implementation rather than guessed from memory.
- **`portfolio_engine.import_transactions`** service — portfolio, provider, file path in; a report out. Never writes to `transactions.yaml`.
- **`sensor.<portfolio>_last_import`** — the one new entity, backed by a direct `Store` wrapper (`ImportReportStore`), not a new generic repository interface.
- **Dashboard Import view**, **`docs/user/BROKER_IMPORT.md`**, expanded diagnostics.
- **ADR-0013** — the one new ADR, covering the `Transaction.id`-reuse decision for broker references and why generated IDs must be deterministic.

Engine version: unchanged (0.7.0) — no `engine/` file was touched. Integration version: 0.2.0 → 0.3.0.

## The one real design problem, worked through in the ADR

The milestone's acceptance criteria require reusing `Transaction` unchanged, but duplicate detection needs *some* way to identify "the same transaction from a different broker reference." The obvious answer — reuse `Transaction.id` for broker references too — has a trap: if a row without a native broker reference gets a random UUID at parse time, re-importing the *same file* twice produces two different random IDs, and the "transaction ID" duplicate check the milestone explicitly asks for becomes a silent no-op for exactly the importer (Generic CSV) most likely to need it. The fix is a deterministic content hash instead of a random UUID — same input, same generated ID, every time. ADR-0013 walks through why this matters and why the heuristic check (date+symbol+shares+amount) is still needed on top of it, not redundant with it: the heuristic catches the *same real-world transaction* arriving through two different sources with different ID schemes, which deterministic hashing alone can't.

## A real bug this milestone caught, unrelated to broker import itself

Verbose HA-harness log output surfaced a warning that had been shipping silently since Milestone 7: `PortfolioDividendIncomeSensor` combined `device_class: monetary` with `state_class: measurement` — a combination `SensorDeviceClass.MONETARY` doesn't permit (only `None` or `total`). Home Assistant doesn't raise an error for this; it logs a warning and silently drops the invalid `state_class`, which meant the entity had been quietly losing Recorder statistics eligibility without any test noticing, since no test had ever asserted on the *combination* of device_class and state_class together. Fixed by unsetting `state_class` (neither `measurement` nor `total` is actually correct for a rolling 12-month window), and added a regression test covering all fifteen entities — specifically because HA's silent-drop behavior means a passing test suite alone wouldn't catch a recurrence; the check has to be explicit.

## Verified, not assumed, per the milestone's own standard

Three places where I checked something concrete rather than relying on general knowledge or convention:

1. **IBKR Flex Query field names** — searched and fetched IBKR's own documentation and a well-regarded open-source Flex Query parser (`ibflex`) before writing `IbkrFlexQueryImporter`, rather than reconstructing the format from memory. The importer's docstring says plainly that Flex Query templates are user-configurable and a heavily customized template may need field-name adjustment — an honest scope statement, not a claim of universal coverage.
2. **Benchmark confirmation** — re-ran `scripts/benchmark.py` and compared against the recorded Milestone 8 baseline rather than assuming "no engine changes" implies "no need to check." Numbers matched within normal noise, as expected, and that comparison is recorded in `BENCHMARKS.md`, not just asserted in this report.
3. **The dividend-income bug** — found by actually reading real HA-harness log output (Milestone 8 established this habit; this milestone continued it), not by re-reviewing Milestone 7's code from memory.

## Validation checklist

- [x] Broker import framework implemented — `BrokerImportProvider` interface, `ImportReport`/`build_import_report`, `detect_duplicates`
- [x] Two import providers implemented — `GenericCsvImporter`, `IbkrFlexQueryImporter`
- [x] Existing `Transaction` model reused unchanged — confirmed by the ADR-0013 decision specifically avoiding a new field
- [x] Existing calculators, reconciliation, MWR, TWR work unchanged — proven end to end in `tests/test_import_pipeline_end_to_end.py`, not just asserted
- [x] Import service available in Home Assistant — `portfolio_engine.import_transactions`, tested for success, validation errors, and response shape
- [x] Import report generated — transactions read, imported, duplicates, rejected, validation errors, warnings, all present and tested
- [x] Documentation added — `docs/user/BROKER_IMPORT.md`, dashboard Import view, `services.yaml`
- [x] Benchmark confirms no measurable regression — re-run and compared, not assumed (`BENCHMARKS.md`'s Milestone 9 note)
- [x] All existing tests pass — 355/355 existing tests unmodified and passing
- [x] Test count increases — 411 total, up from 355
- [x] At most one ADR — exactly one (0013)
- [x] No new calculators, entities beyond the one justified, providers, or repositories beyond what's documented as deliberately *not* a new repository interface

## How to validate

```bash
python -m pytest tests/ tests_integration/ -q   # 342 passed
./.ha_test_venv/bin/python -m pytest tests_ha/ -q   # 69 passed
python -m ruff check . custom_components/ tests_ha/ scripts/ importers/
python -m mypy
python scripts/benchmark.py --sizes 100,500,1000 --snapshot-days 100,500,1000,2000 --repeats 15
```

## What's next

Per the brief's own out-of-scope list: no live broker APIs, OAuth, scheduled synchronization, automatic writes, bidirectional sync, transaction editing/deletion, or tax calculations — all deliberately deferred, not overlooked. A natural next step if broker import proves useful in practice would be a third importer (the architecture already makes that a self-contained addition), or — a bigger, separate decision — an explicit "write" service that takes a reviewed report and appends it to `transactions.yaml`, which would need its own careful design given the acceptance-criteria-level care this project has put into keeping that file human-owned.
