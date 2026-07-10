# ADR 0013: Broker Import Reuses Transaction.id — No New Field, Deterministic IDs for Sourceless Rows

**Status:** Accepted
**Date:** 2026-07-10

## Decision

`BrokerImportProvider` implementations populate `Transaction.id` with the broker's own native transaction reference when the export provides one (e.g. IBKR Flex Query's `transactionID`). When no native reference is available (e.g. a Generic CSV row with no `id` column), the importer generates a **deterministic** id — a hash of the row's semantic content (type, date, symbol, shares, amount, currency) — rather than a random UUID. `Transaction` itself gains no new field for "broker reference"; `id` is reused for both purposes. Duplicate detection (`importers/duplicate_detection.py`) runs two independent checks: exact `id` match, and a date+symbol+shares+amount heuristic match, both against the portfolio's existing transaction log.

## Reason

**Why no new field on `Transaction`:** The milestone's own acceptance criteria require the existing `Transaction` model to be reused unchanged. A "broker reference" is, at the domain level, exactly what `id` already is for a manually-authored transaction — a unique identifier for that ledger entry (Milestone 4's own design: `id` is generated via `uuid.uuid4()` at load if omitted from YAML). There's no meaningful distinction between "the ID a human assigned" and "the ID a broker assigned" once the transaction is in the log — both exist purely to make the entry addressable and to support exactly the duplicate-detection this milestone needs. Adding a second field would either duplicate that purpose or create an ambiguity (which field is authoritative if both are present).

**Why generated IDs must be deterministic, not random:** This was the one non-obvious part of the design. If a sourceless row (no native broker reference) were assigned a random UUID at parse time, re-importing the *exact same file* a second time would generate a *different* random UUID for the same row, and ID-based duplicate detection would never catch it — defeating the entire purpose of "support optional duplicate detection using transaction ID." Hashing the row's own semantic content instead means re-parsing the same file always produces the same id for the same row, so the exact-id check catches exact re-imports even without a native reference.

**Why the heuristic check is still needed, not redundant with deterministic IDs:** Deterministic content-hashing solves re-importing the *same file* twice, but not the case where the *same real-world transaction* is reported through two different sources with different id schemes — for example, a trade appearing once via a Generic CSV export (no native reference, gets a content-hash id) and once via an IBKR Flex Query export of the same account (has a native `transactionID`, gets that id instead). These have different `id` values by construction, so the exact-id check alone would miss the overlap. The date+symbol+shares+amount heuristic is what catches that case — genuinely serving a different scenario than the id check, not a fallback for the same one.

## Alternatives Considered

- **A new `broker_reference: str | None` field on `Transaction`** — rejected per the acceptance criteria and the "no meaningful distinction from `id`" reasoning above.
- **Random UUIDs for sourceless rows, relying entirely on the heuristic for duplicate detection** — rejected: it would make the "transaction ID" duplicate-detection method the milestone explicitly asks for a no-op for the Generic CSV importer specifically (the one importer most likely to lack native references), silently degrading to heuristic-only without that being an intentional, documented choice.
- **Hashing to a full UUID-shaped string instead of a shorter, `gen-`-prefixed digest** — rejected for a small but real reason: prefixing generated ids makes them visually distinguishable from broker-native or user-authored ids in a transactions.yaml file or an import report, which is useful when a user is reviewing what an import actually produced.

## Consequences

- Generated ids are stable across re-parses of the same file but will change if the row's own content changes (e.g. a broker later corrects a trade's price in a re-exported file) — this is intentional: a semantically different transaction should not be treated as the same one for duplicate-detection purposes, even if it clearly corresponds to "the same trade" from the user's perspective. A user reconciling a corrected export should expect to see both the original and the correction, not a silently-merged single entry — consistent with the transaction log's append-only, non-editing design (Milestone 4).
- Any future broker importer follows the same rule without needing a new decision: use the broker's native reference if the format provides one, otherwise generate a deterministic content hash — this ADR is the one place that logic is decided, not something each new importer reasons about independently.
