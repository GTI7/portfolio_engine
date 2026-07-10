"""Constants for the Portfolio Engine integration.

Kept intentionally small (Milestone 2 scope: single portfolio, one
provider, one repository type) — see MILESTONE_2_PLAN.md for what's
deliberately deferred.
"""
from __future__ import annotations

DOMAIN = "portfolio_engine"

CONF_INVESTMENTS_PATH = "investments_path"
CONF_UPDATE_INTERVAL_MINUTES = "update_interval_minutes"

DEFAULT_INVESTMENTS_PATH = "investments"
DEFAULT_UPDATE_INTERVAL_MINUTES = 15
MIN_UPDATE_INTERVAL_MINUTES = 5  # floor to avoid hammering the price provider

PLATFORMS = ["sensor"]
