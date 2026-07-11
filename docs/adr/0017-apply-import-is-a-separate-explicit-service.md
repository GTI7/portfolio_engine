# ADR 0017: `apply_import` Is a New, Separate, All-or-Nothing Service — `import_transactions` Itself Stays Report-Only

**Status:** Accepted
**Date:** 2026-07-11

## Decision

Add a new HA service, `portfolio_engine.apply_import`, portfolio-scoped (`portfolio` required string, resolved via the existing `_find_coordinator_for_portfolio`). It looks up the portfolio's currently pending report via `coordinator.import_report_store.async_get_last_report(portfolio_id)`, raises `ServiceValidationError` if none exists, appends every transaction in `report.imported` (never `report.duplicates`, never `report.rejected`) to `transactions.yaml` via a fresh `YamlPortfolioWriter.async_append_transactions(...)`, then clears the stored report (new `ImportReportStore.async_clear_report(portfolio_id)` method) and requests a coordinator refresh. `import_transactions` itself is **not modified** — it continues to only build and store a report, exactly as Milestone 9 shipped it.

## Reason

`MILESTONE_9.md`'s own "what's next" section already flagged this exact gap: "a bigger, separate decision — an explicit 'write' service that takes a reviewed report and appends it to `transactions.yaml`, which would need its own careful design given the acceptance-criteria-level care this project has put into keeping that file human-owned." This ADR is that careful design, arriving as its own service specifically so the existing guarantee (`import_transactions` never writes automatically, documented in four places — `BROKER_IMPORT.md`, `importers/base.py`, `importers/report.py`, `services.py`'s own module docstring) is never silently broken. A user who runs `import_transactions`, reviews the response (imported/duplicate/rejected counts, warnings), and is satisfied then makes a second, deliberate call to actually apply it — two distinct actions for two distinct intents ("show me what would happen" vs. "do it"), never conflated into one.

Clearing the stored report on successful apply (rather than leaving it in place with, say, an `applied: bool` flag) keeps `ImportReportStore`'s existing scope intact — it already only stores one thing, the *pending* report, per its own docstring's reasoning ("this only ever stores one thing... not an open-ended, growing collection"); "pending" and "already applied" are better modeled as "present" vs. "absent" than as an extra field every consumer of the store has to remember to check.

## Alternatives Considered

- **Make `import_transactions` itself apply automatically (an `apply: bool` parameter, or always-write).** Rejected outright — this directly contradicts the explicit, multiply-documented guarantee this project has already made to users about that service, and this session's own instruction is not to modify existing architecture without a production-issue justification. There is none here.
- **Selective/partial apply — accept a list of transaction ids to include or exclude.** Deferred, not built in this milestone. It's a materially larger UX surface (a user would need some way to *see* candidate transaction ids before choosing among them — a service call alone doesn't provide much of a review surface for that), and there's no demonstrated need for it yet; a user who wants to exclude specific imported rows can still hand-edit `transactions.yaml` afterward, exactly as they already do today for any manual correction. Worth its own future milestone if real usage shows this matters.
- **Store a full history of reports (not just the most recent) so an older report could still be applied after a newer import supersedes it.** Rejected — matches `ImportReportStore`'s own already-decided single-latest-report scope; a stale older report also can no longer be trusted anyway, since a newer import's duplicate detection already re-ran against the transaction log as it stood at that later point, not the earlier one.
- **Re-run duplicate detection against the current transaction log at apply time**, in case it changed since the report was generated. Considered, not adopted for v1 — plausible if apply is delayed a long time after import, but adds meaningful complexity (silently changing what "imported" means between report-generation time and apply time) for a race that clearing the report on every fresh `import_transactions` call already narrows considerably. Flagged as a good candidate to revisit if real usage surfaces problems.

## Consequences

- `import_transactions`'s existing behavior, tests, and documented guarantees are completely untouched by this milestone — this ADR only adds a new, separate service.
- A user must call two services in sequence to actually get new transactions written — a deliberate two-step confirmation, not a shortcut.
- `ImportReportStore` gains one new method (`async_clear_report`); its existing single-latest-report storage shape is otherwise unchanged.
- Calling `apply_import` twice in a row (without a fresh `import_transactions` in between) fails with a clear `ServiceValidationError` on the second call, rather than silently double-appending — the "nothing pending" state is unambiguous.
