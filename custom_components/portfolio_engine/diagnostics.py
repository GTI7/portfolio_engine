"""Diagnostics support — powers Settings -> Devices & Services -> Portfolio
Engine -> ... -> Download Diagnostics.

Milestone 8: significantly expanded from Milestone 2's original scope, per
that milestone's explicit "make the download genuinely useful" goal -
repository/provider identity, the active calculator registry, expanded
snapshot/transaction statistics, and compatibility/environment
information, alongside everything prior milestones already added. Still
no secrets: TO_REDACT is unchanged, and none of the new fields below are
anything more sensitive than "which classes and versions are active" and
"how many of what."
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_CORE_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import PortfolioCoordinator
from .engine import __version__ as ENGINE_VERSION

# investments_path could theoretically reveal filesystem layout; nothing
# else in config entry data is sensitive for this integration (no API keys
# yet, since Yahoo Finance's public quote endpoint needs none), but redact
# defensively so future providers that DO need a key are covered for free.
TO_REDACT = {"investments_path"}

# The minimum HA version this integration is validated against - see
# docs/COMPATIBILITY_POLICY.md for how this number is derived (from what
# tests_ha/ actually runs against) and what it means if the detected
# runtime version is older.
MIN_SUPPORTED_HA_VERSION = "2025.1"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: PortfolioCoordinator = hass.data[DOMAIN][entry.entry_id]

    summary = coordinator.data.get("summary") if coordinator.data else None
    reconciliation = coordinator.data.get("reconciliation") if coordinator.data else None
    mwr = coordinator.data.get("mwr") if coordinator.data else None
    twr = coordinator.data.get("twr") if coordinator.data else None
    dividends = coordinator.data.get("dividends") if coordinator.data else None
    drawdown = coordinator.data.get("drawdown") if coordinator.data else None
    volatility = coordinator.data.get("volatility") if coordinator.data else None
    concentration = coordinator.data.get("concentration") if coordinator.data else None
    last_import = coordinator.data.get("last_import_report") if coordinator.data else None
    snapshots = coordinator.data.get("snapshots", []) if coordinator.data else []
    all_transactions = (
        coordinator.data.get("portfolio_transactions", []) if coordinator.data else []
    )

    integration = await async_get_integration(hass, DOMAIN)

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_error": coordinator.last_error,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
        },
        # Milestone 8 — "which concrete implementations are active," useful
        # when a bug report needs to distinguish "the YAML repository is
        # broken" from "the Store-backed snapshot repository is broken"
        # from "Yahoo Finance is down" at a glance, without reading logs.
        "repository": {
            "name": coordinator.repository.name,
            "supports_transactions": coordinator.repository.supports_transactions,
        },
        "providers": {
            "price_provider": coordinator.price_provider.name,
            "currency_provider": coordinator.currency_provider.name,
            "snapshot_repository": coordinator.snapshot_repository.name,
        },
        # "Calculator versions" - calculators aren't independently versioned
        # (only the engine package as a whole is, per ADR-0007); this is a
        # registry snapshot of what's active and which class implements it,
        # which serves the same "what do I have installed" bug-report need
        # without inventing a false per-calculator version number.
        "calculators": {
            name: type(calc).__name__ for name, calc in coordinator.calculators.items()
        },
        "environment": {
            "engine_version": ENGINE_VERSION,
            "integration_version": integration.version,
            "home_assistant_core_version": HA_CORE_VERSION,
            "minimum_supported_home_assistant_version": MIN_SUPPORTED_HA_VERSION,
        },
        "portfolio": {
            "portfolio_id": coordinator.data.get("portfolio_id") if coordinator.data else None,
            "base_currency": coordinator.data.get("base_currency") if coordinator.data else None,
            "positions_count": (
                len(coordinator.data.get("positions", [])) if coordinator.data else 0
            ),
            "symbols_missing_quotes": (
                coordinator.data.get("symbols_missing_quotes", []) if coordinator.data else []
            ),
            "fx_rates_missing": (
                coordinator.data.get("fx_rates_missing", []) if coordinator.data else []
            ),
        },
        "summary": (
            {
                "total_value": summary.total_value,
                "total_invested": summary.total_invested,
                "roi_pct": summary.roi_pct,
                "cash_balance": summary.cash_balance,
            }
            if summary
            else None
        ),
        "reconciliation": (
            {
                "status": reconciliation.status,
                "discrepancy_count": len(reconciliation.discrepancies),
                "transactions_considered": reconciliation.transactions_considered,
            }
            if reconciliation
            else None
        ),
        "mwr": (
            {
                "status": mwr.status,
                "rate_pct": mwr.rate_pct,
                "cash_flow_count": mwr.cash_flow_count,
            }
            if mwr
            else None
        ),
        # Milestone 8 — expanded beyond count/latest with oldest timestamp
        # and total span, useful for judging "is this history long enough
        # for TWR/volatility to be meaningful" at a glance.
        "snapshots": _snapshot_statistics(snapshots, coordinator),
        "twr": (
            {
                "status": twr.status,
                "twr_pct": twr.twr_pct,
                "annualized_pct": twr.annualized_pct,
                "periods_used": twr.periods_used,
            }
            if twr
            else None
        ),
        "dividends": (
            {
                "status": dividends.status,
                "rolling_12_months": dividends.rolling_12_months,
                "lifetime": dividends.lifetime,
            }
            if dividends
            else None
        ),
        "drawdown": (
            {
                "status": drawdown.status,
                "current_drawdown_pct": drawdown.current_drawdown_pct,
                "maximum_drawdown_pct": drawdown.maximum_drawdown_pct,
                "recovery_status": drawdown.recovery_status,
            }
            if drawdown
            else None
        ),
        "volatility": (
            {
                "status": volatility.status,
                "annualized_volatility_pct": volatility.annualized_volatility_pct,
                "sample_count": volatility.sample_count,
            }
            if volatility
            else None
        ),
        "concentration": (
            {
                "status": concentration.status,
                "largest_position_pct": (
                    concentration.largest_position.pct_of_portfolio
                    if concentration.largest_position
                    else None
                ),
                "diversification_score": concentration.diversification_score,
                "holding_count": concentration.holding_count,
            }
            if concentration
            else None
        ),
        # Milestone 8 — new block: full-log statistics, distinct from
        # TransactionCalculator's entity-facing `recent` (capped at 10).
        "transactions": _transaction_statistics(all_transactions),
        # Milestone 8 — points at the recorded baseline rather than
        # inventing a separate "benchmark version" number; the benchmark
        # baseline is always recorded against a specific engine version
        # (see BENCHMARKS.md's own header), so engine_version above (in
        # "environment") already is that identifier.
        "benchmarks": {
            "see": "BENCHMARKS.md",
            "engine_version": ENGINE_VERSION,
            "note": (
                "BENCHMARKS.md's header records the engine version the baseline "
                "was captured against - compare to environment.engine_version above."
            ),
        },
        # Milestone 9 — same troubleshooting-tier carve-out as every prior
        # milestone's analogous blocks.
        "last_import": (
            {
                "provider": last_import.provider_name,
                "as_of": last_import.as_of.isoformat(),
                "transactions_read": last_import.transactions_read,
                "imported": last_import.imported_count,
                "duplicates": last_import.duplicate_count,
                "rejected": last_import.rejected_count,
            }
            if last_import
            else None
        ),
    }


def _snapshot_statistics(snapshots: list[Any], coordinator: PortfolioCoordinator) -> dict[str, Any]:
    if not snapshots:
        return {
            "count": 0,
            "oldest_timestamp": None,
            "latest_timestamp": None,
            "latest_portfolio_value": None,
            "span_days": 0,
            "created_this_refresh": (
                coordinator.data.get("snapshot_created", False) if coordinator.data else False
            ),
        }

    oldest = min(snapshots, key=lambda s: s.timestamp)
    latest = max(snapshots, key=lambda s: s.timestamp)
    return {
        "count": len(snapshots),
        "oldest_timestamp": oldest.timestamp.isoformat(),
        "latest_timestamp": latest.timestamp.isoformat(),
        "latest_portfolio_value": latest.portfolio_value,
        "span_days": (latest.timestamp - oldest.timestamp).days,
        "created_this_refresh": (
            coordinator.data.get("snapshot_created", False) if coordinator.data else False
        ),
    }


def _transaction_statistics(transactions: list[Any]) -> dict[str, Any]:
    if not transactions:
        return {"count": 0, "count_by_type": {}, "oldest_date": None, "latest_date": None}

    count_by_type = Counter(t.type.value for t in transactions)
    dates = [t.date for t in transactions]
    return {
        "count": len(transactions),
        "count_by_type": dict(count_by_type),
        "oldest_date": min(dates).isoformat(),
        "latest_date": max(dates).isoformat(),
    }
