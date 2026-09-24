"""Home Assistant services for PV Manager."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ENABLED,
    ATTR_ENTRY_ID,
    ATTR_MODULE_ID,
    CONF_METER_ENTITY,
    CONF_METER_IMPORT_ENTITY,
    DOMAIN,
    SERVICE_CANCEL_CALIBRATION,
    SERVICE_EMERGENCY_STOP,
    SERVICE_REQUEST_REPORT,
    SERVICE_RUN_CALIBRATION,
    SERVICE_SET_DEVICE_STATE,
    SERVICE_SET_MODULE,
    SERVICE_SET_SETTINGS,
)
from .core.audit import AuditKind
from .core.calibration import CalibrationLimits, CalibrationRun, CalibrationState
from .core.normalize import normalize_power, safe_float
from .core.types import DeviceKind
from .runtime import PVManagerRuntime

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA_MODULE = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_MODULE_ID): cv.string,
        vol.Required(ATTR_ENABLED): cv.boolean,
    }
)
SERVICE_SCHEMA_SETTINGS = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required("settings"): dict,
    }
)
SERVICE_SCHEMA_REPORT = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional("provider_id"): cv.string,
        vol.Optional("user_confirmed", default=False): cv.boolean,
    }
)
SERVICE_SCHEMA_CALIBRATION = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("max_power_w", default=2000.0): vol.Coerce(float),
        vol.Optional("max_energy_kwh", default=0.5): vol.Coerce(float),
        vol.Optional("max_seconds_on", default=120.0): vol.Coerce(float),
        vol.Optional("repetitions", default=2): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
    }
)
SERVICE_SCHEMA_DEVICE = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required("device_id"): cv.entity_id,
        vol.Required("turn_on"): cv.boolean,
        vol.Optional("user_confirmed", default=True): cv.boolean,
    }
)
SERVICE_SCHEMA_CANCEL = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})
SERVICE_SCHEMA_EMERGENCY = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required("active"): cv.boolean,
    }
)


def _runtimes(hass: HomeAssistant, call: ServiceCall) -> list[PVManagerRuntime]:
    entries: dict[str, Any] = hass.data.get(DOMAIN, {})
    requested = call.data.get(ATTR_ENTRY_ID)
    result: list[PVManagerRuntime] = []
    for key, value in entries.items():
        if key.endswith("_coordinator"):
            continue
        if requested and key != requested:
            continue
        if isinstance(value, PVManagerRuntime):
            result.append(value)
    return result


async def _save_all(hass: HomeAssistant, runtimes: list[PVManagerRuntime]) -> None:
    for runtime in runtimes:
        await runtime.async_save()
    coordinator_tasks = [
        hass.data[DOMAIN][f"{runtime.entry.entry_id}_coordinator"].async_request_refresh()
        for runtime in runtimes
    ]
    if coordinator_tasks:
        await asyncio.gather(*coordinator_tasks)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register the PV Manager services once."""
    if hass.data.get(f"{DOMAIN}_services_registered"):
        return

    async def handle_set_module(call: ServiceCall) -> dict[str, Any]:
        runtimes = _runtimes(hass, call)
        if not runtimes:
            raise HomeAssistantError("No PV Manager config entry found")
        result: dict[str, Any] = {"ok": True}
        for runtime in runtimes:
            result = runtime.set_module(call.data[ATTR_MODULE_ID], call.data[ATTR_ENABLED])
            if not result.get("ok"):
                return result
        await _save_all(hass, runtimes)
        return result

    async def handle_set_settings(call: ServiceCall) -> dict[str, Any]:
        runtimes = _runtimes(hass, call)
        for runtime in runtimes:
            runtime.update_settings(dict(call.data.get("settings") or {}))
        await _save_all(hass, runtimes)
        return {"ok": True}

    async def handle_request_report(call: ServiceCall) -> dict[str, Any]:
        from .ai_client import build_provider_factory

        runtimes = _runtimes(hass, call)
        if not runtimes:
            raise HomeAssistantError("No PV Manager config entry found")
        runtime = runtimes[0]
        provider_id = str(call.data.get("provider_id") or runtime.ai.get("provider_id", "local_rules"))
        factory = build_provider_factory(hass, runtime) if provider_id != "local_rules" else None
        return await runtime.async_request_ai_report(
            provider_id=provider_id,
            user_confirmed=bool(call.data.get("user_confirmed")),
            transport_factory=factory,
        )

    async def handle_emergency_stop(call: ServiceCall) -> dict[str, Any]:
        runtimes = _runtimes(hass, call)
        for runtime in runtimes:
            runtime.set_emergency_stop(bool(call.data["active"]))
            if call.data["active"] and runtime.calibration_run is not None:
                runtime.calibration_run.abort("emergency_stop")
                await _switch_off(hass, runtime.calibration_run.entity_id)
        await _save_all(hass, runtimes)
        return {"ok": True, "active": bool(call.data["active"])}

    async def handle_run_calibration(call: ServiceCall) -> dict[str, Any]:
        runtimes = _runtimes(hass, call)
        if not runtimes:
            raise HomeAssistantError("No PV Manager config entry found")
        runtime = runtimes[0]
        entity_id = str(call.data["entity_id"])
        domain = entity_id.split(".", 1)[0]
        if domain != "switch":
            raise HomeAssistantError(
                "Calibration currently supports switch entities only, so no unsupported device is controlled."
            )
        if runtime.calibration_run is not None and runtime.calibration_run.state not in {
            CalibrationState.FINISHED,
            CalibrationState.ABORTED,
            CalibrationState.IDLE,
        }:
            raise HomeAssistantError("A calibration run is already active")
        if runtime.settings.get("emergency_stop"):
            raise HomeAssistantError("Emergency stop is active")
        limits = CalibrationLimits(
            max_power_w=float(call.data["max_power_w"]),
            max_energy_kwh=float(call.data["max_energy_kwh"]),
            max_seconds_on=float(call.data["max_seconds_on"]),
            repetitions=int(call.data["repetitions"]),
        )
        run = CalibrationRun(
            device_id=str(call.data.get("device_id") or entity_id),
            entity_id=entity_id,
            limits=limits,
        )
        ok, reason = run.can_start()
        if not ok:
            raise HomeAssistantError(f"Calibration cannot start: {reason}")
        runtime.calibration_run = run
        runtime.audit.record(
            kind=AuditKind.CALIBRATION,
            message_de=f"Lernlauf für {entity_id} gestartet.",
            message_en=f"Learning run for {entity_id} started.",
            now=datetime.now().astimezone(),
            reason="user",
        )
        hass.async_create_task(_run_calibration_task(hass, runtime))
        return {"ok": True, "state": run.state.value}

    async def handle_set_device_state(call: ServiceCall) -> dict[str, Any]:
        runtimes = _runtimes(hass, call)
        if not runtimes:
            raise HomeAssistantError("No PV Manager config entry found")
        runtime = runtimes[0]
        result = await runtime.async_set_device_state(
            device_id=str(call.data["device_id"]),
            turn_on=bool(call.data["turn_on"]),
            user_confirmed=bool(call.data.get("user_confirmed", True)),
        )
        if not result.get("ok"):
            raise HomeAssistantError(str(result.get("message_de") or result.get("error")))
        await runtime.async_save()
        return result

    async def handle_cancel_calibration(call: ServiceCall) -> dict[str, Any]:
        runtimes = _runtimes(hass, call)
        for runtime in runtimes:
            if runtime.calibration_run is not None:
                runtime.calibration_run.abort("user_cancelled")
                await _switch_off(hass, runtime.calibration_run.entity_id)
                await runtime.async_save()
        return {"ok": True}

    response = SupportsResponse.OPTIONAL
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MODULE,
        handle_set_module,
        schema=SERVICE_SCHEMA_MODULE,
        supports_response=response,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SETTINGS,
        handle_set_settings,
        schema=SERVICE_SCHEMA_SETTINGS,
        supports_response=response,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DEVICE_STATE,
        handle_set_device_state,
        schema=SERVICE_SCHEMA_DEVICE,
        supports_response=response,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_REPORT,
        handle_request_report,
        schema=SERVICE_SCHEMA_REPORT,
        supports_response=response,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_CALIBRATION,
        handle_run_calibration,
        schema=SERVICE_SCHEMA_CALIBRATION,
        supports_response=response,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_CALIBRATION,
        handle_cancel_calibration,
        schema=SERVICE_SCHEMA_CANCEL,
        supports_response=response,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EMERGENCY_STOP,
        handle_emergency_stop,
        schema=SERVICE_SCHEMA_EMERGENCY,
        supports_response=response,
    )
    hass.data[f"{DOMAIN}_services_registered"] = True


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove PV Manager services."""
    for service in (
        SERVICE_SET_MODULE,
        SERVICE_SET_SETTINGS,
        SERVICE_SET_DEVICE_STATE,
        SERVICE_REQUEST_REPORT,
        SERVICE_RUN_CALIBRATION,
        SERVICE_CANCEL_CALIBRATION,
        SERVICE_EMERGENCY_STOP,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    hass.data[f"{DOMAIN}_services_registered"] = False


async def _switch_on(hass: HomeAssistant, entity_id: str) -> None:
    domain = entity_id.split(".", 1)[0]
    await hass.services.async_call(domain, "turn_on", {"entity_id": entity_id}, blocking=True)


async def _switch_off(hass: HomeAssistant, entity_id: str) -> None:
    domain = entity_id.split(".", 1)[0]
    try:
        await hass.services.async_call(domain, "turn_off", {"entity_id": entity_id}, blocking=True)
    except Exception as err:  # noqa: BLE001 - abort must still complete
        _LOGGER.warning("Could not switch off %s: %s", entity_id, err)


def _device_power(hass: HomeAssistant, entity_id: str) -> float:
    state = hass.states.get(entity_id)
    if state is None:
        return 0.0
    value = safe_float(state.state)
    if value is None:
        return 0.0
    unit = state.attributes.get("unit_of_measurement")
    return normalize_power(value, unit) or 0.0


def _grid_headroom(runtime: PVManagerRuntime, hass: HomeAssistant) -> float:
    limit = float(runtime.settings.get("grid_import_limit_w") or 0.0)
    if limit <= 0:
        return float("inf")
    # Prefer the configured grid meter or import entity.
    for key in (CONF_METER_ENTITY, CONF_METER_IMPORT_ENTITY):
        entity_id = runtime.entry.options.get(key)
        if not entity_id:
            continue
        state = hass.states.get(entity_id)
        if state is None:
            continue
        value = safe_float(state.state)
        if value is None:
            continue
        power = normalize_power(abs(value), state.attributes.get("unit_of_measurement")) or 0.0
        return max(limit - power, 0.0)
    return float("inf")


async def _run_calibration_task(hass: HomeAssistant, runtime: PVManagerRuntime) -> None:
    """Drive the bounded learning run; always switch off on exit."""
    run = runtime.calibration_run
    if run is None:
        return
    now = datetime.now().astimezone()
    run.start(now)
    try:
        # Baseline phase
        while run.state is CalibrationState.BASELINE:
            await asyncio.sleep(2)
            if runtime.settings.get("emergency_stop"):
                run.abort("emergency_stop")
                return
            if (datetime.now().astimezone() - run.started_at).total_seconds() >= run.limits.baseline_seconds:
                run.baseline_done(_device_power(hass, run.entity_id), datetime.now().astimezone())
        for _ in range(run.limits.repetitions):
            headroom = _grid_headroom(runtime, hass)
            allowed, reason = run.device_on_allowed(grid_headroom_w=headroom, device_power_w=0.0)
            if not allowed:
                run.abort(reason)
                return
            await _switch_on(hass, run.entity_id)
            started = time.monotonic()
            previous = time.monotonic()
            while run.state is CalibrationState.DEVICE_ON:
                await asyncio.sleep(2)
                now_mono = time.monotonic()
                elapsed = now_mono - started
                device_w = _device_power(hass, run.entity_id)
                run.record_measurement(device_w, now_mono - previous)
                previous = now_mono
                allowed, reason = run.device_on_allowed(
                    grid_headroom_w=_grid_headroom(runtime, hass),
                    device_power_w=device_w,
                )
                if not allowed:
                    run.abort(reason)
                    await _switch_off(hass, run.entity_id)
                    return
                if elapsed >= run.limits.max_seconds_on:
                    break
            all_done = run.device_off(datetime.now().astimezone())
            await _switch_off(hass, run.entity_id)
            if all_done:
                run.finish()
                break
            while run.state is CalibrationState.DEVICE_OFF:
                await asyncio.sleep(2)
                if (datetime.now().astimezone() - run.started_at).total_seconds() >= run.limits.off_seconds:
                    run.state = CalibrationState.DEVICE_ON
                    run.started_at = datetime.now().astimezone()
                    run.step += 1
    except asyncio.CancelledError:
        run.abort("task_cancelled")
        await _switch_off(hass, run.entity_id)
        raise
    except Exception as err:  # noqa: BLE001 - a learning run must never crash HA
        _LOGGER.exception("Calibration failed: %s", err)
        run.abort("unexpected_error")
        await _switch_off(hass, run.entity_id)
    finally:
        # Store the measured value as a suggestion, never as a verified limit.
        if run.measured_delta_w:
            device = runtime.devices.get(run.device_id)
            if device is not None and device.get("kind") == DeviceKind.FLEXIBLE_LOAD.value:
                device["measured_power_w"] = round(run.measured_delta_w)
        await runtime.async_save()
