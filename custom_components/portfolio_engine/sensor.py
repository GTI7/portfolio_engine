"""Sensor platform for Portfolio Engine.

Fourteen entities through Milestone 8, plus one added in Milestone 9
(last import summary) — fifteen total. This is the integration's public
API from this point forward. Do not add more entities without a
docs/ENTITY_CONTRACTS.md entry, per the policy established at the end of
Milestone 2.5.

Per ADR-0009, entity classes contain no logic beyond calling
`sensor_mapping.py`'s pure functions on `coordinator.data`.

Milestone 8 polish pass (no functional changes, per that milestone's own
scope constraint):
- Every entity now has an `_attr_icon` (none had one before).
- `_attr_entity_category` is deliberately left unset (== primary/main) on
  all fourteen entities, including `portfolio_reconciliation` (the closest
  candidate for `EntityCategory.DIAGNOSTIC`). HA's diagnostic category is
  meant for entities describing a *device's* operational state (firmware
  version, signal strength, IP address) - reconciliation status, like
  every other entity here, is primary *portfolio* domain data, not device
  housekeeping, so it stays in the main entity list where a user actually
  looks for it. This is a considered decision, not an oversight.
- Unit/device-class/state-class assignments were audited against every
  entity's `docs/ENTITY_CONTRACTS.md` entry and found already correct
  (set correctly at each entity's original introduction) - no changes
  were needed there.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import sensor_mapping
from .const import DOMAIN
from .coordinator import PortfolioCoordinator

# All entities read from the same coordinator's already-fetched `.data` -
# no entity does its own I/O, so there's no per-entity update to limit.
# 0 is HA's documented convention for exactly this case (coordinator-based
# entities with no individual work to parallelize/throttle).
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PortfolioCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            PortfolioValueSensor(coordinator, entry),
            PortfolioTotalInvestedSensor(coordinator, entry),
            PortfolioTotalProfitSensor(coordinator, entry),
            PortfolioRoiSensor(coordinator, entry),
            PortfolioCashBalanceSensor(coordinator, entry),
            PortfolioPositionsSensor(coordinator, entry),
            PortfolioTransactionCountSensor(coordinator, entry),
            PortfolioReconciliationSensor(coordinator, entry),
            PortfolioMwrSensor(coordinator, entry),
            PortfolioTwrSensor(coordinator, entry),
            PortfolioDividendIncomeSensor(coordinator, entry),
            PortfolioDrawdownSensor(coordinator, entry),
            PortfolioVolatilitySensor(coordinator, entry),
            PortfolioConcentrationSensor(coordinator, entry),
            PortfolioLastImportSensor(coordinator, entry),
        ]
    )


class _PortfolioEntityBase(CoordinatorEntity[PortfolioCoordinator], SensorEntity):
    """Shared device info so every entity groups under one device per
    portfolio in the HA UI (see architecture doc Section 1 on entity
    naming/device-info conventions — one device per portfolio, which also
    sets up cleanly for multi-portfolio in a later milestone).
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        portfolio_id = self.coordinator.data.get("portfolio_id", self._entry.entry_id)
        portfolio_name = self.coordinator.data.get("portfolio_name", "Portfolio")
        return DeviceInfo(
            identifiers={(DOMAIN, portfolio_id)},
            name=portfolio_name,
            manufacturer="Portfolio Engine",
        )


class PortfolioValueSensor(_PortfolioEntityBase):
    _attr_translation_key = "portfolio_value"
    _attr_icon = "mdi:cash-multiple"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_value"

    @property
    def native_value(self) -> float:
        return sensor_mapping.get_portfolio_value(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str:
        return str(self.coordinator.data.get("base_currency", "EUR"))


class PortfolioTotalInvestedSensor(_PortfolioEntityBase):
    _attr_translation_key = "portfolio_total_invested"
    _attr_icon = "mdi:bank"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_total_invested"

    @property
    def native_value(self) -> float:
        return sensor_mapping.get_total_invested(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str:
        return str(self.coordinator.data.get("base_currency", "EUR"))


class PortfolioTotalProfitSensor(_PortfolioEntityBase):
    _attr_translation_key = "portfolio_total_profit"
    _attr_icon = "mdi:trending-up"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_total_profit"

    @property
    def native_value(self) -> float:
        return sensor_mapping.get_total_profit(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str:
        return str(self.coordinator.data.get("base_currency", "EUR"))


class PortfolioRoiSensor(_PortfolioEntityBase):
    _attr_translation_key = "portfolio_roi"
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_roi"

    @property
    def native_value(self) -> float:
        return sensor_mapping.get_roi(self.coordinator.data)


class PortfolioCashBalanceSensor(_PortfolioEntityBase):
    _attr_translation_key = "portfolio_cash_balance"
    _attr_icon = "mdi:cash"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_cash_balance"

    @property
    def native_value(self) -> float:
        return sensor_mapping.get_cash_balance(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str:
        return str(self.coordinator.data.get("base_currency", "EUR"))


class PortfolioPositionsSensor(_PortfolioEntityBase):
    """The one attribute-only entity in Milestone 2 — see the hybrid entity
    model (architecture doc Section 3.5). State is a count (so it's still a
    meaningful number if ever shown bare); the holdings table itself lives
    entirely in attributes for dashboards to consume.
    """

    _attr_translation_key = "portfolio_positions"
    _attr_icon = "mdi:chart-pie"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "positions"

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_positions"

    @property
    def native_value(self) -> int:
        return sensor_mapping.get_positions_count(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_positions_attributes(self.coordinator.data)


class PortfolioTransactionCountSensor(_PortfolioEntityBase):
    """Milestone 4 — MILESTONE_4_SPEC.md Section 9. State is a count, same
    pattern as PortfolioPositionsSensor; the recent-activity table lives
    entirely in attributes.
    """

    _attr_translation_key = "portfolio_transaction_count"
    _attr_icon = "mdi:swap-horizontal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "transactions"

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_transaction_count"

    @property
    def native_value(self) -> int:
        return sensor_mapping.get_transaction_count(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_transaction_attributes(self.coordinator.data)


class PortfolioReconciliationSensor(_PortfolioEntityBase):
    """Milestone 4 — MILESTONE_4_SPEC.md Section 9. A data-integrity check
    (declared state vs. what the transaction log implies), not a portfolio
    metric — see docs/adr/0010-transaction-log-as-validation-layer.md.
    State is a string ("ok" | "discrepancy" | "no_data"), so no unit/state
    class/device class apply, matching the entity contract.
    """

    _attr_translation_key = "portfolio_reconciliation"
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_reconciliation"

    @property
    def native_value(self) -> str:
        return sensor_mapping.get_reconciliation_status(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_reconciliation_attributes(self.coordinator.data)


class PortfolioMwrSensor(_PortfolioEntityBase):
    """Milestone 5 — money-weighted return (XIRR). Returns None (HA renders
    "unknown") when not computable, per MwrResult's status field; the
    reason lives in attributes, matching PortfolioReconciliationSensor's
    pattern for the same kind of "check, don't just report a number"
    entity.
    """

    _attr_translation_key = "portfolio_mwr"
    _attr_icon = "mdi:chart-line"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_mwr"

    @property
    def native_value(self) -> float | None:
        return sensor_mapping.get_mwr(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_mwr_attributes(self.coordinator.data)


class PortfolioTwrSensor(_PortfolioEntityBase):
    """Milestone 6 — time-weighted return. Same "None means not ok, reason
    in attributes" convention as PortfolioMwrSensor/PortfolioReconciliationSensor.
    """

    _attr_translation_key = "portfolio_twr"
    _attr_icon = "mdi:chart-line-variant"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_twr"

    @property
    def native_value(self) -> float | None:
        return sensor_mapping.get_twr(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_twr_attributes(self.coordinator.data)


class PortfolioDividendIncomeSensor(_PortfolioEntityBase):
    """Milestone 7 — MILESTONE_7_DESIGN.md's dividend analytics section.
    State is rolling-12-month income (the most actionable single figure);
    lifetime/current-year/yield/average-monthly live in attributes - one
    entity, not four, per that design document's explicit scope decision.

    Milestone 9 fix: originally shipped with `state_class = MEASUREMENT`,
    reasoned as "a rolling window, not a monotonic total." That reasoning
    was correct about the *data*, but wrong about what HA's device-class
    validation actually permits - `SensorDeviceClass.MONETARY` only
    allows `state_class` of `None` or `TOTAL`, never `MEASUREMENT`; HA
    logs a warning and silently drops the invalid state_class at runtime
    (breaking Recorder statistics for the entity, not just a cosmetic
    warning). Caught via real HA-harness test output (Milestone 9's own
    testing work), not by design review - unrelated to broker import
    itself, fixed here rather than left for a future milestone to
    rediscover. `state_class` is now unset (`None`) - the rolling-window
    semantics don't fit `TOTAL` either (which implies monotonic
    accumulation), so `None` is the honest choice, at the cost of this
    entity not getting Recorder long-term statistics.
    """

    _attr_translation_key = "portfolio_dividend_income"
    _attr_icon = "mdi:hand-coin"
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_dividend_income"

    @property
    def native_value(self) -> float | None:
        return sensor_mapping.get_dividend_income(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str:
        return str(self.coordinator.data.get("base_currency", "EUR"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_dividend_attributes(self.coordinator.data)


class PortfolioDrawdownSensor(_PortfolioEntityBase):
    """Milestone 7. State is current drawdown (0 or negative); maximum
    drawdown, peak value/date, and recovery status live in attributes.
    """

    _attr_translation_key = "portfolio_drawdown"
    _attr_icon = "mdi:trending-down"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_drawdown"

    @property
    def native_value(self) -> float | None:
        return sensor_mapping.get_drawdown(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_drawdown_attributes(self.coordinator.data)


class PortfolioVolatilitySensor(_PortfolioEntityBase):
    """Milestone 7. State is annualized volatility; daily (unannualized)
    volatility and sample size live in attributes.
    """

    _attr_translation_key = "portfolio_volatility"
    _attr_icon = "mdi:chart-bell-curve"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_volatility"

    @property
    def native_value(self) -> float | None:
        return sensor_mapping.get_volatility(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_volatility_attributes(self.coordinator.data)


class PortfolioConcentrationSensor(_PortfolioEntityBase):
    """Milestone 7. State is the largest position's share of the
    portfolio; largest winner/loser, top-5 concentration, diversification
    score, and Herfindahl-Hirschman index live in attributes - one entity,
    not several, per MILESTONE_7_DESIGN.md's scope decision.
    """

    _attr_translation_key = "portfolio_concentration"
    _attr_icon = "mdi:target"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_concentration"

    @property
    def native_value(self) -> float | None:
        return sensor_mapping.get_concentration(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_concentration_attributes(self.coordinator.data)


class PortfolioLastImportSensor(_PortfolioEntityBase):
    """Milestone 9. State is the last import's imported-transaction count;
    provider, timestamp, duplicates, rejected, and warnings live in
    attributes. Justified against the milestone's own "no additional
    entities unless they provide long-term value" bar: unlike the
    service's own response data (which only exists for the caller of that
    one service call), this entity gives an ongoing, dashboard-visible
    "when did I last import, how did it go" signal that persists across
    restarts (backed by ImportReportStore) - long-term value, not a
    one-off convenience.
    """

    _attr_translation_key = "portfolio_last_import"
    _attr_icon = "mdi:file-import"
    _attr_native_unit_of_measurement = "transactions"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PortfolioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_portfolio_last_import"

    @property
    def native_value(self) -> int | None:
        return sensor_mapping.get_last_import(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return sensor_mapping.get_last_import_attributes(self.coordinator.data)
