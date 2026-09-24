"""PV Manager Home Assistant integration.

Home Assistant is imported lazily so that the framework-independent core can be
unit-tested without a Home Assistant installation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import DOMAIN

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import PVManagerCoordinator
    from .runtime import PVManagerRuntime

_LOGGER = logging.getLogger(__name__)


def _platforms() -> list[Any]:
    from homeassistant.const import Platform

    return [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PV Manager from a config entry."""
    from homeassistant.exceptions import ConfigEntryNotReady

    from .coordinator import PVManagerCoordinator
    from .panel import async_register_panel
    from .runtime import PVManagerRuntime
    from .services import async_setup_services
    from .websocket_api import async_setup_websocket

    runtime = PVManagerRuntime(hass, entry)
    await runtime.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    coordinator = PVManagerCoordinator(hass, runtime)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001 - HA requires a typed setup error
        raise ConfigEntryNotReady(f"PV Manager could not refresh: {err}") from err

    hass.data[DOMAIN][f"{entry.entry_id}_coordinator"] = coordinator
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _platforms())
    await async_register_panel(hass)
    async_setup_websocket(hass)
    async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and keep other entries working."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _platforms())
    if not unload_ok:
        return False
    _pop_entry_data(hass, entry)
    if not _has_entries(hass):
        await _cleanup_global(hass)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete all PV Manager-owned data when the entry is removed."""
    runtime: PVManagerRuntime | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime is not None:
        runtime.alias_vault.clear()
        runtime.audit.clear()
        try:
            await runtime.async_remove_store()
        except Exception:  # noqa: BLE001 - deletion should never fail the UI
            _LOGGER.debug("PV Manager store already removed")
    _pop_entry_data(hass, entry)
    if not _has_entries(hass):
        await _cleanup_global(hass)
    _LOGGER.debug("PV Manager entry removed; own data deleted, foreign entities untouched")


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after options changed."""
    await hass.config_entries.async_reload(entry.entry_id)


def _pop_entry_data(hass: HomeAssistant, entry: ConfigEntry) -> None:
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    hass.data.get(DOMAIN, {}).pop(f"{entry.entry_id}_coordinator", None)


def _has_entries(hass: HomeAssistant) -> bool:
    return any(key for key in hass.data.get(DOMAIN, {}) if not key.endswith("_coordinator"))


async def _cleanup_global(hass: HomeAssistant) -> None:
    from .panel import async_unregister_panel
    from .services import async_unload_services

    await async_unregister_panel(hass)
    async_unload_services(hass)


def runtime_for(hass: HomeAssistant, entry_id: str) -> PVManagerRuntime | None:
    """Return the runtime for a config entry."""
    return hass.data.get(DOMAIN, {}).get(entry_id)


def coordinator_for(hass: HomeAssistant, entry_id: str) -> PVManagerCoordinator | None:
    """Return the coordinator for a config entry."""
    return hass.data.get(DOMAIN, {}).get(f"{entry_id}_coordinator")


def first_entry_id(hass: HomeAssistant) -> str | None:
    """Return the first PV Manager entry id."""
    entries: dict[str, Any] = hass.data.get(DOMAIN, {})
    for key in entries:
        if not key.endswith("_coordinator"):
            return key
    return None
