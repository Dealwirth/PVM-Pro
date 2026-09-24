"""Register the custom PV Manager sidebar panel and static files."""

from __future__ import annotations

import logging
import os
from typing import Any

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL_PATH, PANEL_WEBCOMPONENT, STATIC_URL

_LOGGER = logging.getLogger(__name__)
_DATA_PANEL = f"{DOMAIN}_panel_registered"
_DATA_STATIC = f"{DOMAIN}_static_callbacks"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the panel exactly once."""
    if hass.data.get(_DATA_PANEL):
        return

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    callbacks: list[Any] = []
    if not hass.data.get(_DATA_STATIC):
        try:
            registered = await hass.http.async_register_static_paths(
                [StaticPathConfig(STATIC_URL, frontend_dir, cache_headers=False)]
            )
            callbacks = list(registered or [])
        except RuntimeError:
            # Already registered (for example after a reload); continue.
            callbacks = []
        hass.data[_DATA_STATIC] = callbacks

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_WEBCOMPONENT,
        frontend_url_path=PANEL_URL_PATH,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/pv-manager-panel.js",
        embed_iframe=False,
        require_admin=False,
    )
    hass.data[_DATA_PANEL] = True
    _LOGGER.debug("PV Manager panel registered at /%s", PANEL_URL_PATH)


async def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the panel when the last config entry is removed."""
    if not hass.data.get(_DATA_PANEL):
        return
    try:
        panel_custom.async_remove_panel(hass, PANEL_URL_PATH)
    except Exception:  # noqa: BLE001 - removal must never fail the unload
        _LOGGER.debug("PV Manager panel was already removed")
    hass.data[_DATA_PANEL] = False

    for callback in hass.data.pop(_DATA_STATIC, []) or []:
        try:
            callback()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Static path callback already removed")
