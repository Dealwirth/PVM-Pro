"""Switches that expose the internal module store to Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import PVManagerCoordinator
from .core.modules import CORE_MODULE_ID, MODULE_SPECS, ModuleSpec


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one switch per optional module."""
    coordinator: PVManagerCoordinator = entry.runtime_data
    async_add_entities(
        PVManagerModuleSwitch(coordinator, entry, spec)
        for spec in MODULE_SPECS
        if spec.module_id != CORE_MODULE_ID
    )


class PVManagerModuleSwitch(CoordinatorEntity[PVManagerCoordinator], SwitchEntity):
    """Enable or disable one internal PV Manager module."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: PVManagerCoordinator,
        entry: ConfigEntry,
        spec: ModuleSpec,
    ) -> None:
        """Create the module switch."""
        super().__init__(coordinator)
        self.spec = spec
        self._attr_unique_id = f"{entry.entry_id}_module_{spec.module_id}"
        self._attr_name = spec.name_de
        self._attr_icon = spec.icon
        # Optional modules stay hidden until the user enables them.
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer=NAME,
            model="Local Energy Manager",
            sw_version=VERSION,
        )

    @property
    def is_on(self) -> bool:
        """Return True when the module is enabled."""
        runtime = self.coordinator.runtime
        return self.spec.module_id in runtime.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the module and its dependencies."""
        runtime = self.coordinator.runtime
        runtime.set_module(self.spec.module_id, True)
        await runtime.async_save()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the module when no other module depends on it."""
        runtime = self.coordinator.runtime
        runtime.set_module(self.spec.module_id, False)
        await runtime.async_save()
        await self.coordinator.async_request_refresh()
