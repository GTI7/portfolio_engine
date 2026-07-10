from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import yaml

from ..engine.models import Holding, Portfolio, Transaction, TransactionType
from .base import PortfolioRepository


class YamlRepository(PortfolioRepository):
    """Reads portfolios from /config/investments/<portfolio_id>/holdings.yaml,
    and, per Milestone 4, an optional sibling transactions.yaml.

    Each subdirectory of `base_path` is one portfolio; its `holdings.yaml`
    holds the `name`, `base_currency`, and `holdings` list. This is pure I/O
    and validation (via Holding's own __post_init__) — no calculation.
    """

    name = "yaml"
    supports_transactions = True

    def __init__(self, base_path: Path):
        self._base_path = Path(base_path)

    async def async_get_portfolios(self) -> list[Portfolio]:
        # Synchronous file I/O wrapped as an async method for interface
        # consistency with repositories that genuinely need network I/O
        # (broker/cloud). A real HA integration would offload this to an
        # executor via hass.async_add_executor_job; that's a coordinator
        # concern, not this repository's.
        portfolios: list[Portfolio] = []
        if not self._base_path.exists():
            return portfolios

        for portfolio_dir in sorted(p for p in self._base_path.iterdir() if p.is_dir()):
            holdings_file = portfolio_dir / "holdings.yaml"
            if not holdings_file.exists():
                continue
            data = yaml.safe_load(holdings_file.read_text()) or {}
            holdings = [Holding(**h) for h in data.get("holdings", [])]
            portfolio_id = portfolio_dir.name
            portfolios.append(
                Portfolio(
                    id=portfolio_id,
                    name=data.get("name", portfolio_id.replace("_", " ").title()),
                    holdings=holdings,
                    base_currency=data.get("base_currency", "EUR"),
                    cash_balance=float(data.get("cash_balance", 0.0)),
                    # Populated here (not lazily) so a Portfolio object read
                    # via async_get_portfolios() is always complete on its
                    # own — see PortfolioRepository.async_get_portfolios's
                    # docstring for why that's the contract, not an
                    # implementation detail.
                    transactions=self._load_transactions(portfolio_dir, portfolio_id),
                )
            )
        return portfolios

    async def async_get_transactions(self, portfolio_id: str) -> list[Transaction]:
        portfolio_dir = self._base_path / portfolio_id
        return self._load_transactions(portfolio_dir, portfolio_id)

    def _load_transactions(self, portfolio_dir: Path, portfolio_id: str) -> list[Transaction]:
        transactions_file = portfolio_dir / "transactions.yaml"
        if not transactions_file.exists():
            return []

        data = yaml.safe_load(transactions_file.read_text()) or {}
        raw_entries = data.get("transactions", [])

        seen_ids: set[str] = set()
        transactions: list[Transaction] = []
        for entry in raw_entries:
            txn_id = entry.get("id") or str(uuid.uuid4())
            if txn_id in seen_ids:
                raise ValueError(
                    f"{portfolio_id}/transactions.yaml: duplicate transaction id {txn_id!r}"
                )
            seen_ids.add(txn_id)

            transactions.append(
                Transaction(
                    id=txn_id,
                    portfolio_id=portfolio_id,
                    type=TransactionType(entry["type"]),
                    date=_parse_date(entry["date"]),
                    currency=entry["currency"],
                    amount=float(entry["amount"]),
                    symbol=entry.get("symbol"),
                    shares=entry.get("shares"),
                    price=entry.get("price"),
                    notes=entry.get("notes"),
                )
            )

        # Chronological order, per MILESTONE_4_SPEC.md Section 4.2 — id is
        # not a sort key, only `date` is. Python's sort is stable, so
        # equal-date entries keep their file order rather than being
        # reordered arbitrarily.
        transactions.sort(key=lambda t: t.date)
        return transactions


def _parse_date(value: str) -> datetime:
    # datetime.fromisoformat added "Z" suffix support in Python 3.11; this
    # normalization keeps transactions.yaml portable to slightly older
    # interpreters without depending on that specific version behavior.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
