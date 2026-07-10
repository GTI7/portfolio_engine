"""BrokerImportProvider interface - converts a broker's export format into
the project's existing Transaction objects. Similar in spirit to
PortfolioRepository/PriceProvider/CurrencyProvider: a narrow interface,
concrete implementations per format, the rest of the engine completely
unaware any of them exist.

Deliberately NOT a persistence mechanism. A BrokerImportProvider only
parses; it never reads or writes transactions.yaml, never talks to
SnapshotRepository, and never calls a calculator. See
importers/report.py for how a ParseResult becomes a full ImportReport
(duplicate detection against the existing log), and
docs/adr/0013-broker-import-reuses-transaction-id.md for why duplicate
detection needed no new field on Transaction.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from engine.models import Transaction


@dataclass
class RejectedRow:
    """One row/entry from a broker export that could not become a valid
    Transaction. `raw` is whatever the importer had for that row (a dict
    for CSV, a flattened attribute dict for XML) - kept as strings/simple
    values only, so this is always safely JSON-serializable for a report.
    """

    source_line: int
    raw: dict[str, str]
    error: str


@dataclass
class ParseResult:
    """Output of BrokerImportProvider.parse() - deliberately does not know
    about the existing transaction log or duplicates; that comparison
    happens one layer up, in importers/report.py, so this stays a pure
    "did this broker-specific format parse into valid Transactions"
    question.
    """

    transactions: list[Transaction] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BrokerImportProvider(ABC):
    @abstractmethod
    def parse(self, file_content: str, portfolio_id: str) -> ParseResult:
        """Parse a broker export's raw file content into Transactions for
        the given portfolio. Every row that fails Transaction's own
        validation (engine/models.py's Transaction.__post_init__) becomes
        a RejectedRow with that validation's own error message - this
        importer layer does not duplicate or re-implement any validation
        rule, it only decides how to map broker-specific columns/fields
        onto Transaction's constructor arguments before letting
        Transaction's real validation run.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
