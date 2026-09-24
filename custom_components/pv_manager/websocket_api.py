"""WebSocket API for the custom PV Manager frontend."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .ai_client import provider_info
from .const import (
    ATTR_ENABLED,
    ATTR_ENTRY_ID,
    ATTR_MODULE_ID,
    CONF_AI_API_KEY,
    DOMAIN,
    SERVICE_CANCEL_CALIBRATION,
    SERVICE_RUN_CALIBRATION,
)
from .core.ai import PROVIDER_CATALOG
from .runtime import PVManagerRuntime

_LOGGER = logging.getLogger(__name__)


def _runtime(hass: HomeAssistant, msg: dict[str, Any]) -> PVManagerRuntime | None:
    entries: dict[str, Any] = hass.data.get(DOMAIN, {})
    requested = msg.get(ATTR_ENTRY_ID)
    for key, value in entries.items():
        if key.endswith("_coordinator"):
            continue
        if requested and key != requested:
            continue
        if isinstance(value, PVManagerRuntime):
            return value
    return None


async def _refresh(hass: HomeAssistant, runtime: PVManagerRuntime) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(f"{runtime.entry.entry_id}_coordinator")
    if coordinator is not None:
        await coordinator.async_request_refresh()


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register all PV Manager websocket commands once."""
    if hass.data.get(f"{DOMAIN}_websocket_registered"):
        return
    for command in (
        websocket_get_state,
        websocket_get_modules,
        websocket_set_module,
        websocket_update_settings,
        websocket_discover_devices,
        websocket_register_device,
        websocket_set_manual_override,
        websocket_emergency_stop,
        websocket_complete_tutorial,
        websocket_prepare_ai,
        websocket_request_ai,
        websocket_set_ai_key,
        websocket_set_ai_provider,
        websocket_get_audit,
        websocket_clear_audit,
        websocket_run_calibration,
        websocket_cancel_calibration,
        websocket_control_device,
        websocket_get_providers,
    ):
        websocket_api.async_register_command(hass, command)
    hass.data[f"{DOMAIN}_websocket_registered"] = True


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_state"})
@websocket_api.async_response
async def websocket_get_state(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the current, privacy-conscious snapshot."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    connection.send_result(msg["id"], runtime.last_snapshot or runtime.snapshot())


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_modules"})
@websocket_api.async_response
async def websocket_get_modules(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the internal module store cards."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    from .core.modules import store_cards

    connection.send_result(msg["id"], {"modules": store_cards(runtime.enabled)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_module",
        vol.Required(ATTR_MODULE_ID): cv.string,
        vol.Required(ATTR_ENABLED): cv.boolean,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)
@websocket_api.async_response
async def websocket_set_module(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Enable or disable one module."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    result = runtime.set_module(msg[ATTR_MODULE_ID], msg[ATTR_ENABLED])
    if result.get("ok"):
        await runtime.async_save()
        await _refresh(hass, runtime)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/update_settings",
        vol.Required("patch"): dict,
    }
)
@websocket_api.async_response
async def websocket_update_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update settings, terminal, privacy or AI configuration."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    result = runtime.update_settings(dict(msg["patch"]))
    await runtime.async_save()
    await _refresh(hass, runtime)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/discover_devices"})
@websocket_api.async_response
async def websocket_discover_devices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return automatic discovery suggestions."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    connection.send_result(msg["id"], {"candidates": runtime.entity_candidates()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/register_device",
        vol.Required("device"): dict,
    }
)
@websocket_api.async_response
async def websocket_register_device(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Register a confirmed device profile."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    result = runtime.register_device(dict(msg["device"]))
    if result.get("ok"):
        await runtime.async_save()
        await _refresh(hass, runtime)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_manual_override",
        vol.Required("device_id"): cv.string,
        vol.Required("active"): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_set_manual_override(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Switch one device into or out of manual mode."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    connection.send_result(
        msg["id"],
        runtime.set_manual_override(msg["device_id"], bool(msg["active"])),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/emergency_stop",
        vol.Required("active"): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_emergency_stop(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Activate or clear the emergency stop; no device is switched off implicitly."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    runtime.set_emergency_stop(bool(msg["active"]))
    if msg["active"] and runtime.calibration_run is not None:
        runtime.calibration_run.abort("emergency_stop")
        await hass.services.async_call(
            DOMAIN,
            "cancel_calibration",
            {ATTR_ENTRY_ID: runtime.entry.entry_id},
            blocking=True,
        )
    await runtime.async_save()
    await _refresh(hass, runtime)
    connection.send_result(msg["id"], {"ok": True, "active": bool(msg["active"])})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/complete_tutorial"})
@websocket_api.async_response
async def websocket_complete_tutorial(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Mark the first-run tutorial as completed."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    runtime.complete_tutorial()
    await runtime.async_save()
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/prepare_ai"})
@websocket_api.async_response
async def websocket_prepare_ai(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the exact payload that would be sent to an AI provider."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    connection.send_result(msg["id"], runtime.prepare_ai_preview())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/request_ai",
        vol.Required("provider_id"): cv.string,
        vol.Required("user_confirmed"): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_request_ai(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Run an advisory AI report; the AI never receives control tools."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    from .ai_client import build_provider_factory

    provider_id = str(msg["provider_id"])
    factory = build_provider_factory(hass, runtime) if provider_id != "local_rules" else None
    result = await runtime.async_request_ai_report(
        provider_id=provider_id,
        user_confirmed=bool(msg["user_confirmed"]),
        transport_factory=factory,
    )
    await runtime.async_save()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_ai_key",
        vol.Required("api_key"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_set_ai_key(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Store an API key in the config entry without returning it."""
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Administrator required")
        return
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    key = str(msg["api_key"]).strip()
    options = dict(runtime.entry.options)
    if key:
        options[CONF_AI_API_KEY] = key
    else:
        options.pop(CONF_AI_API_KEY, None)
    hass.config_entries.async_update_entry(runtime.entry, options=options)
    runtime.ai["api_key_set"] = bool(key)
    connection.send_result(msg["id"], {"ok": True, "api_key_set": bool(key)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_ai_provider",
        vol.Required("provider_id"): cv.string,
        vol.Optional("endpoint"): cv.string,
        vol.Optional("model"): cv.string,
        vol.Optional("enabled"): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_set_ai_provider(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Configure the optional AI provider."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    runtime.ai["provider_id"] = msg["provider_id"]
    runtime.ai["endpoint"] = msg.get("endpoint", "")
    runtime.ai["model"] = msg.get("model", "")
    runtime.ai["enabled"] = bool(msg.get("enabled", runtime.ai.get("enabled", False)))
    await runtime.async_save()
    connection.send_result(msg["id"], {"ok": True, "ai": runtime._ai_state()})  # noqa: SLF001


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_audit"})
@websocket_api.async_response
async def websocket_get_audit(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the redacted audit log."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    connection.send_result(msg["id"], {"entries": runtime.audit.as_dicts()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/clear_audit",
        vol.Required("confirm"): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_clear_audit(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete the in-memory audit log after explicit confirmation."""
    if not msg["confirm"]:
        connection.send_error(msg["id"], "confirmation_required", "Confirmation required")
        return
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    runtime.audit.clear()
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/run_calibration",
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("max_power_w", default=2000.0): vol.Coerce(float),
        vol.Optional("max_energy_kwh", default=0.5): vol.Coerce(float),
        vol.Optional("max_seconds_on", default=120.0): vol.Coerce(float),
        vol.Optional("repetitions", default=2): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
    }
)
@websocket_api.async_response
async def websocket_run_calibration(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Start a bounded learning run through the service layer."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    try:
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_RUN_CALIBRATION,
            {
                ATTR_ENTRY_ID: runtime.entry.entry_id,
                "entity_id": msg["entity_id"],
                "device_id": msg.get("device_id") or msg["entity_id"],
                "max_power_w": msg["max_power_w"],
                "max_energy_kwh": msg["max_energy_kwh"],
                "max_seconds_on": msg["max_seconds_on"],
                "repetitions": msg["repetitions"],
            },
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "calibration_failed", str(err))
        return
    connection.send_result(msg["id"], result or {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/cancel_calibration"})
@websocket_api.async_response
async def websocket_cancel_calibration(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Cancel a running learning run and switch the device off."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CANCEL_CALIBRATION,
        {ATTR_ENTRY_ID: runtime.entry.entry_id},
        blocking=True,
    )
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/control_device",
        vol.Required("device_id"): cv.string,
        vol.Required("turn_on"): cv.boolean,
        vol.Optional("user_confirmed", default=False): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_control_device(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Execute one explicit device command through the central safety gate."""
    runtime = _runtime(hass, msg)
    if runtime is None:
        connection.send_error(msg["id"], "not_found", "No PV Manager config entry found")
        return
    result = await runtime.async_set_device_state(
        device_id=str(msg["device_id"]),
        turn_on=bool(msg["turn_on"]),
        user_confirmed=bool(msg.get("user_confirmed", False)),
    )
    await runtime.async_save()
    await _refresh(hass, runtime)
    if result.get("ok"):
        connection.send_result(msg["id"], result)
    else:
        connection.send_error(
            msg["id"],
            str(result.get("error", "control_failed")),
            str(result.get("message_de") or result.get("error")),
        )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_providers"})
@websocket_api.async_response
async def websocket_get_providers(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the public AI provider catalogue."""
    connection.send_result(
        msg["id"],
        {
            "providers": [provider_info(info.provider_id) for info in PROVIDER_CATALOG],
        },
    )
