"""Coordinator that refreshes the PV Manager snapshot."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL_SECONDS, DOMAIN, NAME
from .runtime import PVManagerRuntime

_LOGGER = logging.getLogger(__name__)


class PVManagerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Refresh device readings, forecast and security state."""

    def __init__(self, hass: HomeAssistant, runtime: PVManagerRuntime) -> None:
        """Create the coordinator for one config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{NAME} {runtime.entry.entry_id[:6]}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS),
        )
        self.runtime = runtime

    async def _async_update_data(self) -> dict[str, Any]:
        """Update all PV Manager state."""
        try:
            return await self.runtime.async_refresh()
        except Exception as err:  # noqa: BLE001 - HA needs a clear UpdateFailed
            raise UpdateFailed(f"{DOMAIN} update failed: {err}") from err
