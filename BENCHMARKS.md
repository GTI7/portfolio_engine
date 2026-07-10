# Portfolio Engine Benchmark — engine v1.0.0

Python 3.12.3 · 25 repeats per size, full `PortfolioEngine.run()` (11 calculators: summary, allocation, performance, reconciliation, transactions, mwr, twr, dividends, drawdown, volatility, concentration)

## By holdings count (fixed 30-day snapshot history, 1 transaction per holding)

| Holdings | Mean (ms) | Median (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|
| 100 | 1.235 | 1.194 | 1.131 | 1.545 |
| 500 | 5.049 | 4.851 | 4.663 | 6.775 |
| 1000 | 9.862 | 9.733 | 9.185 | 14.176 |

## By snapshot history length (fixed 20 holdings) — watching for O(n^2) over long histories

| Snapshot Days | Mean (ms) | Median (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|
| 100 | 0.736 | 0.725 | 0.679 | 0.883 |
| 500 | 1.982 | 1.941 | 1.870 | 2.573 |
| 1000 | 2.264 | 2.239 | 2.149 | 2.701 |
| 2000 | 2.477 | 2.470 | 2.383 | 2.670 |

## Interpretation

- Both dimensions scale linearly-to-sub-linearly, as expected: holdings ratios (500/100 ≈ 4.1x for 5x size, 1000/500 ≈ 1.95x for 2x size) and snapshot-history ratios (100→2000 days is only ~3.4x time for 20x history) both match a healthy O(n) or better shape, no O(n²) signal.
- **These absolute numbers are the current, correct baseline as of engine v1.0.0** (Milestone 10) — roughly 25–40% higher than the numbers recorded through Milestone 9. This shift was investigated, not silently accepted: confirmed stable across three independent runs at increasing repeat counts, with zero `engine/` files touched in Milestone 10, a uniform percentage increase across every measurement (not concentrated at larger sizes, which a real algorithmic regression would produce), and scaling ratios unchanged from prior baselines. This points to environment-level load variance in this sandboxed session (more background contention than during earlier milestones' benchmark runs) rather than a code regression — but is recorded as the honest result of the investigation available in this environment, not a fully conclusive "definitely not a regression" claim. A from-scratch profiling session on a dedicated, uncontended machine would be the more conclusive way to fully rule it out.

## History (for anyone comparing against an older recorded baseline)

- **Milestone 6** (engine v0.6.0): the first version of the snapshot-history benchmark dimension found a real O(n²) bug in `ReconciliationCalculator` (a linear scan over positions inside a loop over symbols) — fixed with a `{symbol: Holding}` dict built once. 1000-holding time dropped from ~19.7ms to ~6.3ms.
- **Milestone 7** (engine v0.7.0): extended to 11 calculators; both dimensions re-checked and found no new algorithmic issue — a genuine negative result, recorded rather than skipped.
- **Milestones 8 and 9**: no `engine/` changes; re-confirmed consistent with the Milestone 7 baseline within normal noise on both occasions.
- **Milestone 10** (engine v1.0.0, no code change — a stability-declaration version bump only): re-confirmed again; see "Interpretation" above for the noise investigation this time specifically.

## What this does and doesn't measure

**Does measure:** the engine's own computation cost — `build_positions()` + all eleven registered calculators — in isolation, using synthetic in-memory data. The snapshot-history table isolates history-length cost from holdings-count cost by holding holdings count fixed at a modest 20; the holdings-count table isolates holdings-count cost by holding snapshot history fixed at 30 days.

**Does not measure:**
- Provider I/O (fetching real quotes or exchange rates over the network).
- Repository I/O (reading `holdings.yaml`/`transactions.yaml` from disk, or `StoreSnapshotRepository`'s actual `Store` read/write cost — HA-only, not exercised by this standalone-engine benchmark).
- Home Assistant coordinator/entity-update overhead.
- Broker import parsing cost (`importers/`, Milestone 9) — entirely separate from `PortfolioEngine.run()`, never invoked by it.
- `DividendCalculator`'s cost at very large transaction-log sizes with many dividend entries specifically (this benchmark's synthetic transactions are all `BUY`, no `DIVIDEND`).

## How to reproduce

```bash
python scripts/benchmark.py --sizes 100,500,1000 --snapshot-days 100,500,1000,2000 --repeats 25
```

Machine: containerized Linux dev environment, Python 3.12.3. Not a controlled/isolated benchmarking environment — sufficient for the stated goal (a baseline for regression comparison), not for making absolute performance claims. Re-run at a higher repeat count if a result looks implausible before recording it — this has been necessary more than once across this project's history (see "History" above), and taking that extra step is cheaper than publishing a wrong number.
