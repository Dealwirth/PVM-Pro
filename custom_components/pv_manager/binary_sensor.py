"""Binary sensors for PV Manager safety and privacy state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import PVManagerCoordinator


@dataclass(frozen=True, kw_only=True)
class PVManagerBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor with an extractor."""

    value_fn: Callable[[dict[str, Any]], bool]


BINARY_DESCRIPTIONS: tuple[PVManagerBinaryDescription, ...] = (
    PVManagerBinaryDescription(
        key="security_critical",
        name="Sicherheit kritisch",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:shield-alert",
        value_fn=lambda data: (data.get("security") or {}).get("overall") == "critical",
    ),
    PVManagerBinaryDescription(
        key="emergency_stop",
        name="Not-Aus",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:alert-octagon",
        value_fn=lambda data: bool(data.get("emergency_stop")),
    ),
    PVManagerBinaryDescription(
        key="external_ai_active",
        name="Externe KI aktiv",
        icon="mdi:cloud-alert",
        value_fn=lambda data: bool((data.get("privacy") or {}).get("external_active")),
    ),
    PVManagerBinaryDescription(
        key="balance_problem",
        name="Energiebilanz auffällig",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:scale-unbalanced",
        value_fn=lambda data: not bool((data.get("summary") or {}).get("balance_ok", True)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all binary sensors."""
    coordinator: PVManagerCoordinator = entry.runtime_data
    async_add_entities(
        PVManagerBinarySensor(coordinator, entry, description) for description in BINARY_DESCRIPTIONS
    )


class PVManagerBinarySensor(CoordinatorEntity[PVManagerCoordinator], BinarySensorEntity):
    """One PV Manager binary sensor."""

    entity_description: PVManagerBinaryDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PVManagerCoordinator,
        entry: ConfigEntry,
        description: PVManagerBinaryDescription,
    ) -> None:
        """Create the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer=NAME,
            model="Local Energy Manager",
            sw_version=VERSION,
        )

    @property
    def is_on(self) -> bool:
        """Return the current boolean state."""
        data = self.coordinator.data or {}
        try:
            return bool(self.entity_description.value_fn(data))
        except (TypeError, ValueError, AttributeError):
            return False
