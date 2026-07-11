"""YAML-backed PortfolioWriter - the write-side counterpart to
YamlRepository (repositories/yaml_repository.py), which never writes. See
docs/adr/0015 for why these are two separate classes rather than one, and
docs/adr/0016 for the atomic-write/single-rotation-backup mechanism every
write in this module goes through - the first write path this project has
ever had to `holdings.yaml`/`transactions.yaml`, files every other part of
this codebase treats as hand-owned.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from engine.models import Holding, Transaction

from .writer_base import PortfolioWriter


class YamlPortfolioWriter(PortfolioWriter):
    name = "yaml"

    def __init__(self, base_path: Path):
        self._base_path = Path(base_path)

    async def async_create_portfolio(
        self,
        portfolio_id: str,
        name: str,
        base_currency: str,
        cash_balance: float,
        holdings: list[Holding],
    ) -> None:
        # Synchronous file I/O wrapped as an async method for interface
        # consistency with YamlRepository's own "sync I/O behind an async
        # signature" convention - offloading to an executor is the
        # caller's job (services.py/config_flow.py), not this class's, so
        # this stays as HA-independent as engine/ itself.
        self._create_portfolio_sync(portfolio_id, name, base_currency, cash_balance, holdings)

    async def async_append_transactions(
        self, portfolio_id: str, transactions: list[Transaction]
    ) -> None:
        self._append_transactions_sync(portfolio_id, transactions)

    def _create_portfolio_sync(
        self,
        portfolio_id: str,
        name: str,
        base_currency: str,
        cash_balance: float,
        holdings: list[Holding],
    ) -> None:
        portfolio_dir = self._base_path / portfolio_id
        holdings_file = portfolio_dir / "holdings.yaml"
        if holdings_file.exists():
            raise FileExistsError(
                f"{portfolio_id}: holdings.yaml already exists - "
                "async_create_portfolio never overwrites an existing portfolio"
            )

        portfolio_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "name": name,
            "base_currency": base_currency,
            "cash_balance": cash_balance,
            "holdings": [_holding_to_yaml_dict(h) for h in holdings],
        }
        self._write_atomically(holdings_file, yaml.safe_dump(data, sort_keys=False))

    def _append_transactions_sync(
        self, portfolio_id: str, transactions: list[Transaction]
    ) -> None:
        portfolio_dir = self._base_path / portfolio_id
        transactions_file = portfolio_dir / "transactions.yaml"

        existing_entries: list[dict] = []
        if transactions_file.exists():
            existing_data = yaml.safe_load(transactions_file.read_text(encoding="utf-8")) or {}
            existing_entries = existing_data.get("transactions", [])

        portfolio_dir.mkdir(parents=True, exist_ok=True)
        new_entries = [_transaction_to_yaml_dict(t) for t in transactions]
        data = {"transactions": existing_entries + new_entries}
        self._write_atomically(transactions_file, yaml.safe_dump(data, sort_keys=False))

    def _write_atomically(self, target_path: Path, content: str) -> None:
        """Per docs/adr/0016: back up any existing file to a single-rotation
        `.bak` sibling (overwritten on every write, never accumulated),
        write the new content to a temp file in the same directory, then
        atomically replace the target with `os.replace` - so a crash or
        power loss mid-write leaves the original file intact, never a
        half-written one. No `.bak` is created the first time a file is
        written, since there is nothing yet to back up.
        """
        if target_path.exists():
            backup_path = target_path.parent / (target_path.name + ".bak")
            backup_path.write_text(
                target_path.read_text(encoding="utf-8"), encoding="utf-8"
            )

        tmp_path = target_path.parent / (target_path.name + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, target_path)


def _holding_to_yaml_dict(holding: Holding) -> dict[str, object]:
    # Deliberately not shared with services.py's own _holding_to_dict (JSON
    # export shape) - same "coupling for its own sake, not genuine reuse"
    # reasoning services.py already gives for keeping its own serialization
    # helpers local and independent per use case.
    data: dict[str, object] = {
        "symbol": holding.symbol,
        "shares": holding.shares,
        "avg_price": holding.avg_price,
        "currency": holding.currency,
        "type": holding.type,
    }
    if holding.account is not None:
        data["account"] = holding.account
    return data


def _transaction_to_yaml_dict(txn: Transaction) -> dict[str, object]:
    data: dict[str, object] = {
        "id": txn.id,
        "type": txn.type.value,
        "date": txn.date.isoformat(),
        "currency": txn.currency,
        "amount": txn.amount,
    }
    if txn.symbol is not None:
        data["symbol"] = txn.symbol
    if txn.shares is not None:
        data["shares"] = txn.shares
    if txn.price is not None:
        data["price"] = txn.price
    if txn.notes is not None:
        data["notes"] = txn.notes
    return data
