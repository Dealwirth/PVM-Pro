"""Sensor entities for PV Manager."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import PVManagerCoordinator


@dataclass(frozen=True, kw_only=True)
class PVManagerSensorDescription(SensorEntityDescription):
    """Description with a value extractor."""

    value_fn: Callable[[dict[str, Any]], Any]


def _summary(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: (data.get("summary") or {}).get(key)


def _forecast(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: (data.get("forecast") or {}).get(key)


SENSOR_DESCRIPTIONS: tuple[PVManagerSensorDescription, ...] = (
    PVManagerSensorDescription(
        key="pv_power",
        name="PV Leistung",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-panel",
        value_fn=_summary("pv_w"),
    ),
    PVManagerSensorDescription(
        key="grid_import",
        name="Netzbezug",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower-import",
        value_fn=_summary("grid_import_w"),
    ),
    PVManagerSensorDescription(
        key="grid_export",
        name="Einspeisung",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower-export",
        value_fn=_summary("grid_export_w"),
    ),
    PVManagerSensorDescription(
        key="household_load",
        name="Hausverbrauch",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:home-lightning-bolt",
        value_fn=_summary("load_w"),
    ),
    PVManagerSensorDescription(
        key="battery_soc",
        name="Batterie Ladestand",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-50",
        value_fn=_summary("battery_soc"),
    ),
    PVManagerSensorDescription(
        key="solar_forecast_24h",
        name="PV Prognose 24 h",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:weather-sunny",
        value_fn=_forecast("solar_kwh_next_24h"),
    ),
    PVManagerSensorDescription(
        key="consumption_forecast_24h",
        name="Verbrauchsprognose 24 h",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:chart-bell-curve",
        value_fn=_forecast("consumption_kwh_next_24h"),
    ),
    PVManagerSensorDescription(
        key="forecast_confidence",
        name="Prognose-Vertrauen",
        native_unit_of_measurement="%",
        icon="mdi:check-decagram-outline",
        value_fn=lambda data: round(float((data.get("forecast") or {}).get("confidence") or 0.0) * 100),
    ),
    PVManagerSensorDescription(
        key="security_score",
        name="Sicherheitsbewertung",
        native_unit_of_measurement="%",
        icon="mdi:shield-check",
        value_fn=lambda data: (data.get("security") or {}).get("score"),
    ),
    PVManagerSensorDescription(
        key="active_plans",
        name="Aktive Ladepläne",
        icon="mdi:calendar-check",
        value_fn=lambda data: len(data.get("plans") or []),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all PV Manager sensors."""
    coordinator: PVManagerCoordinator = entry.runtime_data
    async_add_entities(
        PVManagerSensor(coordinator, entry, description) for description in SENSOR_DESCRIPTIONS
    )


class PVManagerSensor(CoordinatorEntity[PVManagerCoordinator], SensorEntity):
    """One PV Manager sensor."""

    entity_description: PVManagerSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PVManagerCoordinator,
        entry: ConfigEntry,
        description: PVManagerSensorDescription,
    ) -> None:
        """Create the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer=NAME,
            model="Local Energy Manager",
            sw_version=VERSION,
            configuration_url=f"/{DOMAIN}",
        )

    @property
    def native_value(self) -> Any:
        """Return the value from the latest coordinator snapshot."""
        data = self.coordinator.data or {}
        try:
            return self.entity_description.value_fn(data)
        except (TypeError, ValueError, AttributeError):
            return None
