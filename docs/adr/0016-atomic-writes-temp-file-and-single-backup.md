# ADR 0016: Portfolio File Writes Use Temp-File-Plus-Rename and a Single-Rotation `.bak` Copy

**Status:** Accepted
**Date:** 2026-07-11

## Decision

`YamlPortfolioWriter` never writes directly to `holdings.yaml`/`transactions.yaml` in place. Every write: (1) copies the existing target file, if any, to a sibling `<name>.bak` (overwriting any previous `.bak` — a single rotation, not a growing history); (2) serializes the new content to a temp file in the *same directory* (`holdings.yaml.tmp`); (3) atomically replaces the target with `os.replace(tmp_path, target_path)`.

### Backup policy (explicit)

The backup policy this milestone ships is exactly one thing, stated plainly so it's never ambiguous to a future reader: **a single rotating `.bak` file per portfolio file**, holding only the content of that file immediately before the most recent programmatic write. `holdings.yaml.bak` and `transactions.yaml.bak` each hold at most one prior version — the version *before that* is gone the moment a second write happens. This is a one-step "undo my last mistake," not a history, not a log, and not a substitute for `export_portfolio_data`.

## Reason

This is the first milestone in this project's history that writes programmatically to the two files this integration explicitly documents as "human-owned" (`docs/user/BROKER_IMPORT.md`'s own FAQ, `importers/report.py`'s and `MILESTONE_9.md`'s "do not automatically modify portfolio data" framing). No existing write path in this codebase established any safety precedent to reuse: `_write_export_file` (`services.py`, Milestone 10) is a direct `.write_text()` overwrite, but it targets a *new*, user-named export file, never `holdings.yaml`/`transactions.yaml` — an acceptable risk there specifically because a failed or partial write only affects a throwaway backup file the user is about to inspect anyway, not their live portfolio configuration. Writing to the actual, hand-maintained portfolio files carries a materially higher cost of corruption (a crash mid-write leaving `holdings.yaml` half-written would make every subsequent coordinator refresh fail to parse it), which justifies spending more care here than `_write_export_file` needed.

`os.replace` is atomic on both POSIX and NTFS *when source and destination are on the same volume* (guaranteed here — the temp file is written into the same portfolio directory as its target), so a crash or power loss mid-write leaves the original file intact, never a half-written one. The `.bak` copy exists because atomicity only protects against a corrupted write, not a *successful* write of the wrong thing (e.g. `apply_import` appending duplicate rows to `transactions.yaml` because the pending report was stale) — a single-rotation backup is a cheap, immediate "undo my last mistake" recovery path with none of the design cost of a real history feature.

## Alternatives Considered

- **Direct `.write_text()` overwrite, matching `_write_export_file`'s existing precedent exactly.** Rejected — that precedent's safety reasoning explicitly depends on the target being a throwaway, user-named file, not the live `holdings.yaml`/`transactions.yaml` these files' own documentation calls human-owned. Reusing it without also reusing its risk assumptions would be copying the code, not the reasoning.
- **No `.bak` file — atomic replace alone.** Rejected. Atomicity protects against a *corrupted* write, not a correctly-executed write of unwanted content (the realistic failure mode here is closer to "the wrong data got written cleanly" than "the process crashed mid-write"). Given how much emphasis this project's own docs place on these files being hand-owned and precious, the cost of one extra file copy per write is low relative to the cost of an unrecoverable mistake.
- **A full, growing/versioned backup history (timestamped snapshots on every write, keeping more than one prior version).** Out of scope for this milestone, not rejected outright — this project already has a real point-in-time backup mechanism, `export_portfolio_data` (Milestone 10), and a real history mechanism for computed data, `SnapshotRepository`/Store (ADR-0012); a `.bak` file's job here is only undoing the *single most recent* programmatic write. A versioned backup history (e.g. `holdings.yaml.bak.<timestamp>`, keeping N generations) may be worth revisiting in a future milestone if real usage shows a single rotation isn't enough — noted here as a deliberate deferral, not a closed door.
- **A per-portfolio `asyncio.Lock` in the coordinator, serializing concurrent writes to the same portfolio's files.** Considered and deferred, not rejected outright — two overlapping `create_portfolio`/`apply_import` calls against the *same* portfolio_id racing is a real, if narrow, possibility. Deferred because it's an actual-concurrency problem this design doesn't yet have evidence of happening in practice, matching this project's existing precedent of deferring speculative complexity until real usage demonstrates the need (ADR-0005, deferring event-driven recalculation for the same reason). Worth revisiting if it ever actually manifests.

## Consequences

- `YamlPortfolioWriter` needs `hass.async_add_executor_job`-wrapped synchronous file I/O (copy, temp-write, replace) — same offload pattern `_async_import_transactions`'s `_read_file` and `_async_export_portfolio_data`'s `_write_export_file` already use, not a new I/O convention.
- A user who wants a *full* history of every past write (not just the last one) still needs `export_portfolio_data`, run before triggering a write they're unsure about — the `.bak` file is explicitly not a substitute for that.
- Every future write this integration ever adds to `holdings.yaml`/`transactions.yaml` should reuse this same temp-file/replace/`.bak` mechanism rather than re-deciding it, the same way ADR-0014 established a reusable two-`FetchFn` shape for future Yahoo providers.
- **Future note:** versioned/multi-generation backup history is explicitly out of scope for this milestone. If real-world usage ever demonstrates that a single rotation isn't sufficient recovery insurance, that would be a small, self-contained follow-up to this ADR — not a reason to have over-built it now.
