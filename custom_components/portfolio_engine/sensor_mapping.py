"""Maps `update_logic.async_fetch_portfolio_data()`'s output dict to the
values each sensor entity exposes. Pure functions, no `homeassistant.*`
imports — `sensor.py`'s `SensorEntity` subclasses call these from their
`native_value`/`extra_state_attributes` properties, keeping the entity
classes themselves as thin glue (same principle as update_logic.py; see
ADR-0009).
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any


def get_portfolio_value(data: dict[str, Any]) -> float:
    return float(data["summary"].total_value)


def get_total_invested(data: dict[str, Any]) -> float:
    return float(data["summary"].total_invested)


def get_total_profit(data: dict[str, Any]) -> float:
    return float(data["summary"].total_unrealized_gain)


def get_roi(data: dict[str, Any]) -> float:
    return float(data["summary"].roi_pct)


def get_cash_balance(data: dict[str, Any]) -> float:
    return float(data["summary"].cash_balance)


def get_positions_count(data: dict[str, Any]) -> int:
    return len(data["positions"])


def get_positions_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Attribute payload for the one attribute-only entity in Milestone 2
    (sensor.portfolio_positions) — see MILESTONE_2_PLAN.md's entity table.
    Each Position (and its nested Holding/Quote) is converted to a plain
    dict via dataclasses.asdict so it's directly JSON/attribute-serializable.
    """
    return {
        "positions": [_position_to_dict(p) for p in data["positions"]],
        "portfolio_id": data.get("portfolio_id"),
        "portfolio_name": data.get("portfolio_name"),
        "base_currency": data.get("base_currency"),
        "symbols_missing_quotes": data.get("symbols_missing_quotes", []),
        "fx_rates_missing": data.get("fx_rates_missing", []),
    }


def get_transaction_count(data: dict[str, Any]) -> int:
    return int(data["transactions"].count)


def get_transaction_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Attribute payload for sensor.<portfolio>_transaction_count —
    Milestone 4, MILESTONE_4_SPEC.md Section 9.
    """
    return {"recent": [_transaction_to_dict(t) for t in data["transactions"].recent]}


def get_reconciliation_status(data: dict[str, Any]) -> str:
    return str(data["reconciliation"].status)


def get_reconciliation_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Attribute payload for sensor.<portfolio>_reconciliation — Milestone
    4, MILESTONE_4_SPEC.md Section 9.
    """
    reconciliation = data["reconciliation"]
    return {
        "discrepancies": [_discrepancy_to_dict(d) for d in reconciliation.discrepancies],
        "transactions_considered": reconciliation.transactions_considered,
    }


def get_mwr(data: dict[str, Any]) -> float | None:
    """None (-> HA renders "unknown") when status != "ok" - see
    engine/models.py's MwrResult docstring on why "not computable" is
    deliberately distinct from "computed and it's 0%."
    """
    mwr = data["mwr"]
    return mwr.rate_pct if mwr.status == "ok" else None


def get_mwr_attributes(data: dict[str, Any]) -> dict[str, Any]:
    mwr = data["mwr"]
    return {
        "status": mwr.status,
        "cash_flow_count": mwr.cash_flow_count,
        "as_of": mwr.as_of.isoformat() if mwr.as_of else None,
    }


def get_twr(data: dict[str, Any]) -> float | None:
    """None (-> HA renders "unknown") when status != "ok" - same convention
    as get_mwr, MwrResult/TwrResult share the same status semantics.
    """
    twr = data["twr"]
    return twr.twr_pct if twr.status == "ok" else None


def get_twr_attributes(data: dict[str, Any]) -> dict[str, Any]:
    twr = data["twr"]
    return {
        "status": twr.status,
        "periods_used": twr.periods_used,
        "as_of": twr.as_of.isoformat() if twr.as_of else None,
        "annualized_pct": twr.annualized_pct,  # CAGR — Milestone 7, see docs/ENTITY_CONTRACTS.md
    }


def get_dividend_income(data: dict[str, Any]) -> float | None:
    dividends = data["dividends"]
    return dividends.rolling_12_months if dividends.status == "ok" else None


def get_dividend_attributes(data: dict[str, Any]) -> dict[str, Any]:
    dividends = data["dividends"]
    return {
        "status": dividends.status,
        "lifetime": dividends.lifetime,
        "current_year": dividends.current_year,
        "dividend_yield_pct": dividends.dividend_yield_pct,
        "average_monthly_dividend": dividends.average_monthly_dividend,
        "as_of": dividends.as_of.isoformat() if dividends.as_of else None,
    }


def get_drawdown(data: dict[str, Any]) -> float | None:
    drawdown = data["drawdown"]
    return drawdown.current_drawdown_pct if drawdown.status == "ok" else None


def get_drawdown_attributes(data: dict[str, Any]) -> dict[str, Any]:
    drawdown = data["drawdown"]
    return {
        "status": drawdown.status,
        "maximum_drawdown_pct": drawdown.maximum_drawdown_pct,
        "peak_value": drawdown.peak_value,
        "peak_date": drawdown.peak_date.isoformat() if drawdown.peak_date else None,
        "recovery_status": drawdown.recovery_status,
        "as_of": drawdown.as_of.isoformat() if drawdown.as_of else None,
    }


def get_volatility(data: dict[str, Any]) -> float | None:
    volatility = data["volatility"]
    return volatility.annualized_volatility_pct if volatility.status == "ok" else None


def get_volatility_attributes(data: dict[str, Any]) -> dict[str, Any]:
    volatility = data["volatility"]
    return {
        "status": volatility.status,
        "daily_volatility_pct": volatility.daily_volatility_pct,
        "observation_period_days": volatility.observation_period_days,
        "sample_count": volatility.sample_count,
        "as_of": volatility.as_of.isoformat() if volatility.as_of else None,
    }


def get_concentration(data: dict[str, Any]) -> float | None:
    concentration = data["concentration"]
    return (
        concentration.largest_position.pct_of_portfolio
        if concentration.status == "ok" and concentration.largest_position
        else None
    )


def get_concentration_attributes(data: dict[str, Any]) -> dict[str, Any]:
    concentration = data["concentration"]
    return {
        "status": concentration.status,
        "largest_position": (
            asdict(concentration.largest_position) if concentration.largest_position else None
        ),
        "largest_winner": (
            asdict(concentration.largest_winner) if concentration.largest_winner else None
        ),
        "largest_loser": (
            asdict(concentration.largest_loser) if concentration.largest_loser else None
        ),
        "top5_concentration_pct": concentration.top5_concentration_pct,
        "diversification_score": concentration.diversification_score,
        "herfindahl_index": concentration.herfindahl_index,
        "holding_count": concentration.holding_count,
    }


def get_last_import(data: dict[str, Any]) -> int | None:
    """Milestone 9. State is the last import's imported count - None
    (HA "unknown") when no import has ever run for this portfolio, same
    "unknown means no data yet, not an error" convention as every other
    optional-until-used entity since Milestone 5.
    """
    report = data.get("last_import_report")
    return report.imported_count if report else None


def get_last_import_attributes(data: dict[str, Any]) -> dict[str, Any]:
    report = data.get("last_import_report")
    if report is None:
        return {"status": "never_imported"}
    return {
        "status": "ok",
        "provider": report.provider_name,
        "as_of": report.as_of.isoformat(),
        "transactions_read": report.transactions_read,
        "imported": report.imported_count,
        "duplicates": report.duplicate_count,
        "rejected": report.rejected_count,
        "warnings": report.warnings,
    }


def _position_to_dict(position: Any) -> dict[str, Any]:
    d = asdict(position)
    # asdict() serializes the nested Quote's `as_of` datetime as-is (not
    # JSON-safe for all consumers) — normalize to isoformat for anything
    # that ends up rendered in a dashboard attribute.
    quote = d.get("quote")
    if quote and quote.get("as_of") is not None:
        quote["as_of"] = quote["as_of"].isoformat()
    return d


def _transaction_to_dict(transaction: Any) -> dict[str, Any]:
    """Same JSON/attribute-serialization concern as _position_to_dict:
    `date` is a datetime and `type` is a TransactionType enum, neither of
    which is directly attribute-safe — both are normalized to plain
    strings here rather than left for each caller to handle separately.
    """
    d = asdict(transaction)
    d["date"] = transaction.date.isoformat()
    d["type"] = transaction.type.value
    return d


def _discrepancy_to_dict(discrepancy: Any) -> dict[str, Any]:
    return asdict(discrepancy)
