"""Runtime state and orchestration for one PV Manager config entry."""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CALENDAR_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_METER_ENTITY,
    CONF_METER_EXPORT_ENTITY,
    CONF_METER_IMPORT_ENTITY,
    CONF_METER_MODE,
    CONF_PRICE_ENTITY,
    CONF_PV_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_AUDIT_LIMIT,
    DEFAULT_REPORT_INTERVAL,
    DEFAULT_STALE_AFTER_SECONDS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .core.ai import (
    AIAdvisor,
    AIReport,
    AIRequest,
    LocalRulesProvider,
    ReportInterval,
    ReportSchedule,
)
from .core.audit import AuditKind, AuditLog
from .core.calibration import CalibrationRun, CalibrationState
from .core.discovery import discover_candidates
from .core.execution import evaluate_manual_action
from .core.fallback import limit_warnings, resolve_fallback
from .core.forecast import (
    ForecastPoint,
    SolarForecastInput,
    build_baseline,
    confidence_label,
    consumption_forecast,
    solar_forecast,
)
from .core.limits import ConstraintEngine
from .core.modules import (
    CORE_MODULE_ID,
    MODULE_SPECS,
    MODULES_BY_ID,
    default_enabled_modules,
    dependents_of,
    resolve_dependencies,
    store_cards,
)
from .core.normalize import (
    compute_balance,
    normalize_grid_sample,
    normalize_power,
    parse_grid_mode,
    safe_float,
)
from .core.planner import ChargingRequest, SolarWindow, energy_from_soc, plan_charging
from .core.privacy import AliasVault, PrivacyMode, PrivacySettings
from .core.security import (
    FindingSeverity,
    HealthStatus,
    ModuleContract,
    ModuleHealth,
    ReactionSpeed,
    SecurityLevel,
    SecurityReport,
    SecurityTerminal,
    TerminalConfig,
)
from .core.types import (
    Capability,
    DeviceKind,
    DeviceLimits,
    DeviceProfile,
    EntityDescriptor,
    FallbackMode,
    SignConvention,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SETTINGS: dict[str, Any] = {
    "tutorial_done": False,
    "language": "de",
    "theme": "auto",
    "report_interval": DEFAULT_REPORT_INTERVAL,
    "emergency_stop": False,
    "pv_peak_w": 0.0,
    "grid_import_limit_w": 0.0,
    "grid_export_limit_w": 0.0,
    "default_reservation_minutes": 30,
    "grid_charging_allowed": False,
    "notifications_enabled": True,
}

DEFAULT_TERMINAL: dict[str, Any] = {
    "level": SecurityLevel.OBSERVE.value,
    "reaction": "30s",
    "repeat_minutes": 15,
    "repeat_until_resolved": True,
    "max_repeats": 6,
    "allow_module_pause": False,
    "allow_safe_stop": False,
    "allow_emergency_stop": False,
}

DEFAULT_PRIVACY: dict[str, Any] = {
    "mode": PrivacyMode.LOCAL_ONLY.value,
    "include_numbers": True,
    "include_error_codes": True,
    "include_weather": True,
    "include_energy_history": False,
    "include_calendar_presence_only": False,
    "include_module_versions": True,
    "rotate_alias_every_report": True,
    "allow_external_provider": False,
    "preview_required": True,
}

DEFAULT_AI: dict[str, Any] = {
    "provider_id": "local_rules",
    "endpoint": "",
    "model": "",
    "enabled": False,
    "api_key_set": False,
    "report_interval": DEFAULT_REPORT_INTERVAL,
}


class PVManagerRuntime:
    """Owns all mutable state for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create the runtime for a config entry."""
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id))
        self.audit = AuditLog(limit=DEFAULT_AUDIT_LIMIT)
        self.alias_vault = AliasVault()
        self.terminal = SecurityTerminal()
        self.advisor = AIAdvisor(
            providers={"local_rules": LocalRulesProvider()},
            settings=PrivacySettings(),
        )
        self.report_schedule = ReportSchedule(interval=ReportInterval.DAILY)
        self._load_samples: deque[tuple[datetime, float]] = deque(maxlen=5760)
        self._pv_samples: deque[tuple[datetime, float]] = deque(maxlen=5760)
        self.enabled: set[str] = default_enabled_modules()
        self.settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.terminal_config: dict[str, Any] = dict(DEFAULT_TERMINAL)
        self.privacy: dict[str, Any] = dict(DEFAULT_PRIVACY)
        self.ai: dict[str, Any] = dict(DEFAULT_AI)
        self.devices: dict[str, dict[str, Any]] = {}
        self.manual_overrides: set[str] = set()
        self.calibration_run: CalibrationRun | None = None
        self.last_snapshot: dict[str, Any] | None = None
        self._last_security_report: SecurityReport | None = None
        self.last_ai_report: AIReport | None = None
        self._ai_preview: AIRequest | None = None
        self.available = True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    async def async_load(self) -> None:
        """Load persisted settings; never store raw sensor history."""
        stored = await self.store.async_load() or {}
        self.enabled = set(stored.get("modules", default_enabled_modules()))
        self.settings.update(stored.get("settings", {}))
        self.terminal_config.update(stored.get("terminal", {}))
        self.privacy.update(stored.get("privacy", {}))
        self.ai.update(stored.get("ai", {}))
        self.devices = dict(stored.get("devices", {}))
        self.calibration_run = None
        self._apply_privacy_settings()
        self.terminal.config = self._build_terminal_config()
        self.audit.record(
            kind=AuditKind.SYSTEM,
            message_de="PV-Manager wurde geladen.",
            message_en="PV Manager was loaded.",
            now=dt_util.utcnow(),
        )

    async def async_save(self) -> None:
        """Persist only configuration, never personal or measured data."""
        await self.store.async_save(
            {
                "modules": sorted(self.enabled),
                "settings": self.settings,
                "terminal": self.terminal_config,
                "privacy": self.privacy,
                "ai": {key: value for key, value in self.ai.items() if key != "api_key"},
                "devices": self.devices,
            }
        )

    async def async_remove_store(self) -> None:
        """Delete all PV Manager-owned data."""
        await self.store.async_remove()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def set_module(self, module_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable one module and keep dependencies consistent."""
        if module_id not in MODULES_BY_ID:
            return {"ok": False, "error": "unknown_module"}
        if module_id == CORE_MODULE_ID and not enabled:
            return {"ok": False, "error": "core_required"}
        if enabled:
            self.enabled |= resolve_dependencies(self.enabled, module_id=module_id)
        else:
            if dependents_of(module_id, self.enabled):
                return {
                    "ok": False,
                    "error": "dependent_modules_enabled",
                    "dependents": sorted(dependents_of(module_id, self.enabled)),
                }
            self.enabled.discard(module_id)
        self.audit.record(
            kind=AuditKind.MODULE,
            message_de=f"Modul {module_id} {'aktiviert' if enabled else 'deaktiviert'}.",
            message_en=f"Module {module_id} {'enabled' if enabled else 'disabled'}.",
            now=dt_util.utcnow(),
            module_id=module_id,
            reason="user",
        )
        return {"ok": True, "enabled": sorted(self.enabled)}

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Merge a settings patch into the runtime configuration."""
        allowed_sections = {
            "settings": self.settings,
            "terminal": self.terminal_config,
            "privacy": self.privacy,
            "ai": self.ai,
        }
        for section, values in patch.items():
            target = allowed_sections.get(section)
            if target is None or not isinstance(values, dict):
                continue
            for key, value in values.items():
                if key == "api_key":
                    # API keys are stored by the HA layer only and never returned.
                    target["api_key_set"] = bool(value)
                    continue
                target[key] = value
        self._apply_privacy_settings()
        self.terminal.config = self._build_terminal_config()
        self.audit.record(
            kind=AuditKind.SETTING,
            message_de="Einstellungen wurden geändert.",
            message_en="Settings were changed.",
            now=dt_util.utcnow(),
            reason="user",
            context={"sections": sorted(patch)},
        )
        return {"ok": True}

    def set_emergency_stop(self, active: bool) -> None:
        """Enable or clear the global emergency stop."""
        self.settings["emergency_stop"] = active
        self.audit.record(
            kind=AuditKind.SECURITY,
            message_de=f"Not-Aus {'aktiviert' if active else 'deaktiviert'}.",
            message_en=f"Emergency stop {'activated' if active else 'cleared'}.",
            now=dt_util.utcnow(),
            reason="user",
        )

    def register_device(self, device: dict[str, Any]) -> dict[str, Any]:
        """Register or update a manually confirmed device profile."""
        device_id = str(device.get("device_id") or device.get("entity_id") or "")
        if not device_id:
            return {"ok": False, "error": "missing_device_id"}
        kind_value = str(device.get("kind", DeviceKind.UNKNOWN.value))
        try:
            kind = DeviceKind(kind_value)
        except ValueError:
            kind = DeviceKind.UNKNOWN
        limits_raw = device.get("limits") or {}
        limits = DeviceLimits(
            min_power_w=safe_float(limits_raw.get("min_power_w")) or 0.0,
            max_power_w=safe_float(limits_raw.get("max_power_w")) or 0.0,
            max_energy_kwh_per_day=safe_float(limits_raw.get("max_energy_kwh_per_day")) or 0.0,
            battery_capacity_kwh=safe_float(limits_raw.get("battery_capacity_kwh")) or 0.0,
            min_soc=safe_float(limits_raw.get("min_soc")) or 0.0,
            max_soc=safe_float(limits_raw.get("max_soc")) or 100.0,
            min_temperature_c=safe_float(limits_raw.get("min_temperature_c")) or 0.0,
            max_temperature_c=safe_float(limits_raw.get("max_temperature_c")) or 0.0,
            phase_count=int(safe_float(limits_raw.get("phase_count")) or 1),
            phase_limit_a=safe_float(limits_raw.get("phase_limit_a")) or 0.0,
            grid_import_limit_w=safe_float(limits_raw.get("grid_import_limit_w")) or 0.0,
            grid_export_limit_w=safe_float(limits_raw.get("grid_export_limit_w")) or 0.0,
            verified=bool(limits_raw.get("verified", False)),
        )
        capabilities = {
            Capability(capability)
            for capability in device.get("capabilities", [])
            if capability in Capability._value2member_map_
        }
        self.devices[device_id] = {
            "device_id": device_id,
            "entity_id": device.get("entity_id", ""),
            "name": str(device.get("name", device_id)),
            "nickname": str(device.get("nickname", ""))[:40],
            "kind": kind.value,
            "capabilities": sorted(capability.value for capability in capabilities),
            # DeviceLimits uses slots, so it has no __dict__; asdict is the
            # only safe way to turn it into the plain mapping the UI reads.
            "limits": asdict(limits),
            "fallback": str(device.get("fallback", "no_automation")),
            "priority": int(safe_float(device.get("priority")) or 50),
            "automations_allowed": bool(device.get("automations_allowed", False)),
            "target_soc": safe_float(device.get("target_soc")) or 80.0,
            "manually_configured": True,
        }
        self.audit.record(
            kind=AuditKind.SETTING,
            message_de=f"Gerät {self.devices[device_id]['name']} wurde manuell eingerichtet.",
            message_en=f"Device {self.devices[device_id]['name']} was configured manually.",
            now=dt_util.utcnow(),
            reason="user",
            context={"kind": kind.value},
        )
        return {"ok": True, "device": self.devices[device_id]}

    def set_manual_override(self, device_id: str, active: bool) -> dict[str, Any]:
        """Toggle manual control for one device."""
        if active:
            self.manual_overrides.add(device_id)
        else:
            self.manual_overrides.discard(device_id)
        self.audit.record(
            kind=AuditKind.DECISION,
            message_de=f"Manueller Modus {'aktiviert' if active else 'beendet'}.",
            message_en=f"Manual mode {'activated' if active else 'ended'}.",
            now=dt_util.utcnow(),
            reason="user",
            context={"device_id": device_id},
        )
        return {"ok": True}

    def complete_tutorial(self) -> None:
        """Mark the first-run tutorial as completed."""
        self.settings["tutorial_done"] = True

    async def async_set_device_state(
        self,
        *,
        device_id: str,
        turn_on: bool,
        user_confirmed: bool = False,
    ) -> dict[str, Any]:
        """Execute an explicit device command through all safety gates."""
        profile = self._build_profiles().get(device_id)
        if profile is None:
            return {"ok": False, "error": "unknown_device"}
        if turn_on and not user_confirmed:
            return {"ok": False, "error": "confirmation_required"}

        now = dt_util.utcnow()
        value, _unit, fresh, _age = self._reading(device_id, now)
        valid = value is not None
        manual = device_id in self.manual_overrides
        decision = resolve_fallback(
            profile,
            reading_valid=valid,
            reading_fresh=fresh,
            limit_verified=profile.limits.verified or profile.manually_configured,
            manual_override=manual,
            emergency_stop=bool(self.settings.get("emergency_stop")),
        )
        context_allowed = profile.automations_allowed or manual
        engine = ConstraintEngine()
        grid = self._read_grid(now)
        engine.add_grid_limits(
            net_power_w=grid.net_power_w,
            import_limit_w=float(self.settings.get("grid_import_limit_w") or 0.0),
            export_limit_w=float(self.settings.get("grid_export_limit_w") or 0.0),
        )
        if profile.limits.max_power_w > 0:
            engine.add_device_power(label=device_id, max_power_w=profile.limits.max_power_w)
            result = evaluate_manual_action(
                controllable=profile.controllable,
                desired_on=turn_on,
                emergency_stop=bool(self.settings.get("emergency_stop")),
                automation_allowed=context_allowed and valid and fresh,
                requested_power_w=profile.limits.max_power_w,
                engine=engine,
                fallback_reason=decision.reason_code,
            )
        else:
            blocking = [constraint.label for constraint in engine.hard_violations()]
            result = evaluate_manual_action(
                controllable=profile.controllable,
                desired_on=turn_on,
                emergency_stop=bool(self.settings.get("emergency_stop")),
                automation_allowed=context_allowed and valid and fresh and not blocking,
                requested_power_w=0.0,
                engine=None,
                fallback_reason=decision.reason_code if not blocking else blocking[0],
            )
        if not result.allowed:
            self.audit.record(
                kind=AuditKind.DECISION,
                message_de=f"Befehl für {profile.name} blockiert: {result.message_de}",
                message_en=f"Command for {profile.name} blocked: {result.message_en}",
                now=now,
                module_id="core",
                reason=result.reason_code,
                context={"device_kind": profile.kind.value, "turn_on": turn_on},
            )
            return {
                "ok": False,
                "error": result.reason_code,
                "message_de": result.message_de,
                "message_en": result.message_en,
            }

        domain = device_id.split(".", 1)[0]
        service = "turn_on" if turn_on else "turn_off"
        try:
            await self.hass.services.async_call(domain, service, {"entity_id": device_id}, blocking=True)
        except Exception as err:  # noqa: BLE001 - report a clear failure to the UI
            return {"ok": False, "error": "service_call_failed", "message_de": str(err)}
        self.audit.record(
            kind=AuditKind.ACTION,
            message_de=(f"{profile.name} wurde {'eingeschaltet' if turn_on else 'ausgeschaltet'}."),
            message_en=(f"{profile.name} was turned {'on' if turn_on else 'off'}."),
            now=now,
            actor="user",
            module_id="core",
            reason=result.reason_code,
            context={"device_kind": profile.kind.value, "turn_on": turn_on},
        )
        return {
            "ok": True,
            "turn_on": turn_on,
            "allowed_power_w": result.allowed_power_w,
            "clamped": result.clamped,
            "message_de": result.message_de,
            "message_en": result.message_en,
        }

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------
    async def async_refresh(self) -> dict[str, Any]:
        """Build a fresh snapshot and notify about due security findings."""
        snapshot = self.snapshot()
        self.last_snapshot = snapshot
        critical = snapshot["security"]["overall"] == FindingSeverity.CRITICAL.value
        now = dt_util.utcnow()
        if self.report_schedule.is_due(now, critical=critical):
            self.report_schedule.mark_run(now)
        if self.settings.get("notifications_enabled", True) and self._last_security_report is not None:
            for finding in self.terminal.due_notifications(self._last_security_report.findings, now=now):
                self._notify(finding)
        return snapshot

    def _notify(self, finding: Any) -> None:
        """Create one user-visible notification with repair guidance."""
        try:
            from homeassistant.components import persistent_notification
        except Exception:  # noqa: BLE001 - notification support is optional
            return
        english = str(self.settings.get("language", "de")) == "en"
        detail = (finding.detail_en if english else finding.detail_de) or ""
        repair = (finding.repair_en if english else finding.repair_de) or ""
        title = (finding.title_en if english else finding.title_de) or finding.code
        try:
            persistent_notification.async_create(
                self.hass,
                (f"{detail}\n\n{'What you can do' if english else 'Was du tun kannst'}: {repair}").strip(),
                title=f"PV-Manager: {title}",
                notification_id=f"pv_manager_{finding.code}_{finding.module_id}",
            )
        except Exception:  # noqa: BLE001 - never break the update loop
            _LOGGER.debug("Could not create PV Manager notification for %s", finding.code)

    def snapshot(self) -> dict[str, Any]:
        """Build the current state without performing I/O."""
        now = dt_util.utcnow()
        profiles = self._build_profiles()
        readings: dict[str, dict[str, Any]] = {}
        constraints = ConstraintEngine()

        grid = self._read_grid(now)
        pv_w = self._read_power(self.entry.options.get(CONF_PV_ENTITY), now)
        load_entity = self.entry.options.get(CONF_LOAD_ENTITY)
        load_w = self._read_power(load_entity, now)
        battery_charge_w, battery_discharge_w = self._read_battery_power(now)
        battery_soc = self._read_soc(now)

        balance = compute_balance(
            pv_w=pv_w,
            grid_import_w=grid.import_power_w,
            grid_export_w=grid.export_power_w,
            battery_charge_w=battery_charge_w,
            battery_discharge_w=battery_discharge_w,
            measured_load_w=load_w,
        )
        if pv_w:
            self._pv_samples.append((now, pv_w))
        if balance.computed_load_w:
            self._load_samples.append((now, balance.computed_load_w))

        summary = {
            "pv_w": round(pv_w or 0.0),
            "grid_import_w": round(grid.import_power_w or 0.0),
            "grid_export_w": round(grid.export_power_w or 0.0),
            "load_w": round(load_w or balance.computed_load_w),
            "battery_charge_w": round(battery_charge_w or 0.0),
            "battery_discharge_w": round(battery_discharge_w or 0.0),
            "battery_soc": battery_soc,
            "balance_ok": balance.balanced,
            "balance_warnings": list(balance.warnings),
            "grid_convention": grid.convention.value,
            "grid_confidence": grid.confidence,
            "grid_warning": grid.warning,
            "generated_at": now.isoformat(),
        }

        constraints.add_grid_limits(
            net_power_w=grid.net_power_w,
            import_limit_w=float(self.settings.get("grid_import_limit_w") or 0.0),
            export_limit_w=float(self.settings.get("grid_export_limit_w") or 0.0),
        )
        for profile in profiles.values():
            if profile.limits.max_power_w > 0:
                constraints.add_device_power(
                    label=profile.device_id,
                    max_power_w=profile.limits.max_power_w,
                )

        forecast = self._build_forecast(now)
        plans = self._build_plans(now)
        devices = self._device_snapshots(profiles, readings, now)
        security = self._evaluate_security(devices, grid, balance, constraints, now)
        self._last_security_report = security
        if security.overall is FindingSeverity.CRITICAL:
            self.audit.record(
                kind=AuditKind.SECURITY,
                message_de="Kritischer Sicherheitshinweis erkannt.",
                message_en="Critical security finding detected.",
                now=now,
                reason=security.findings[0].code if security.findings else "unknown",
            )
        ai_state = self._ai_state()
        return {
            "version": 1,
            "generated_at": now.isoformat(),
            "tutorial_done": bool(self.settings.get("tutorial_done")),
            "language": self.settings.get("language", "de"),
            "theme": self.settings.get("theme", "auto"),
            "settings": dict(self.settings),
            "terminal": dict(self.terminal_config),
            "emergency_stop": bool(self.settings.get("emergency_stop")),
            "summary": summary,
            "devices": devices,
            "modules": store_cards(self.enabled),
            "forecast": forecast,
            "plans": plans,
            "security": security.as_dict(),
            "constraints": constraints.snapshot(),
            "audit": self.audit.as_dicts()[:60],
            "ai": ai_state,
            "privacy": self._privacy_state(),
            "calibration": self._calibration_state(),
            "manual_overrides": sorted(self.manual_overrides),
        }

    # ------------------------------------------------------------------
    # Readings
    # ------------------------------------------------------------------
    def _state(self, entity_id: str | None) -> State | None:
        if not entity_id:
            return None
        return self.hass.states.get(entity_id)

    def _reading(self, entity_id: str | None, now: datetime) -> tuple[float | None, str | None, bool, float]:
        """Return value, unit, fresh and age seconds."""
        state = self._state(entity_id)
        if state is None:
            return None, None, False, float("inf")
        age = (now - state.last_updated).total_seconds()
        unit = None
        try:
            unit = state.attributes.get("unit_of_measurement")
        except AttributeError:
            unit = None
        return safe_float(state.state), unit, age <= DEFAULT_STALE_AFTER_SECONDS, age

    def _read_power(self, entity_id: str | None, now: datetime) -> float | None:
        value, unit, fresh, _ = self._reading(entity_id, now)
        if value is None or not fresh:
            return None
        return normalize_power(value, unit)

    def _read_soc(self, now: datetime) -> float | None:
        entity_id = self.entry.options.get(CONF_BATTERY_SOC_ENTITY)
        value, unit, fresh, _ = self._reading(entity_id, now)
        if value is None or not fresh:
            return None
        return max(min(value, 100.0), 0.0)

    def _read_battery_power(self, now: datetime) -> tuple[float | None, float | None]:
        entity_id = self.entry.options.get(CONF_BATTERY_ENTITY)
        value, unit, fresh, _ = self._reading(entity_id, now)
        if value is None or not fresh:
            return None, None
        watts = normalize_power(value, unit)
        if watts is None:
            return None, None
        # Canonical: positive charge, negative discharge. If the user selected a
        # signed battery power entity this matches the common convention.
        return (watts if watts > 0 else 0.0, -watts if watts < 0 else 0.0)

    def _read_grid(self, now: datetime):
        options = self.entry.options
        import_entity = options.get(CONF_METER_IMPORT_ENTITY)
        export_entity = options.get(CONF_METER_EXPORT_ENTITY)
        combined = options.get(CONF_METER_ENTITY)
        import_value, import_unit, import_fresh, _ = self._reading(import_entity, now)
        export_value, export_unit, export_fresh, _ = self._reading(export_entity, now)
        combined_value, combined_unit, combined_fresh, _ = self._reading(combined, now)
        convention = parse_grid_mode(options.get(CONF_METER_MODE))
        if import_entity or export_entity:
            if convention in {SignConvention.UNKNOWN, SignConvention.SIGNED_NET}:
                convention = SignConvention.SEPARATE
            return normalize_grid_sample(
                import_value=import_value if import_fresh else None,
                export_value=export_value if export_fresh else None,
                unit=import_unit or export_unit or "W",
                convention=convention,
            )
        return normalize_grid_sample(
            combined_value=combined_value if combined_fresh else None,
            unit=combined_unit or "W",
            convention=convention,
        )

    def _read_weather(self) -> dict[str, Any]:
        state = self._state(self.entry.options.get(CONF_WEATHER_ENTITY))
        if state is None:
            return {}
        attributes = state.attributes
        return {
            "condition": state.state,
            "temperature_c": safe_float(attributes.get("temperature")),
            "cloud_coverage_pct": safe_float(attributes.get("cloud_coverage")),
            "wind_speed": safe_float(attributes.get("wind_speed")),
        }

    def _next_departure(self, now: datetime) -> datetime | None:
        """Read the next future calendar start without guessing a departure.

        Calendar contents are never sent to any provider. Only the resulting
        deadline is used locally for planning. When no calendar event exists,
        the planner returns a safe warning instead of inventing a time.
        """
        state = self._state(self.entry.options.get(CONF_CALENDAR_ENTITY))
        if state is None:
            return None
        candidates: list[datetime] = []

        def collect(value: Any) -> None:
            parsed = _parse_datetime(value)
            if parsed is None:
                return
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=now.tzinfo)
            candidates.append(parsed)

        collect(state.attributes.get("start_time"))
        collect(state.attributes.get("end_time"))
        events = state.attributes.get("events")
        if isinstance(events, list):
            for event in events:
                if not isinstance(event, dict):
                    continue
                collect(event.get("start"))
                collect(event.get("start_time"))
                collect(event.get("end_time"))
        future = [candidate for candidate in candidates if candidate > now]
        return min(future) if future else None

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------
    def _build_profiles(self) -> dict[str, DeviceProfile]:
        options = self.entry.options
        profiles: dict[str, DeviceProfile] = {}

        def add(config_key: str, kind: DeviceKind, capabilities: set[Capability], name: str) -> None:
            entity_id = options.get(config_key)
            if not entity_id:
                return
            profiles[entity_id] = DeviceProfile(
                device_id=entity_id,
                name=name,
                kind=kind,
                capabilities=capabilities,
                limits=DeviceLimits(verified=kind in {DeviceKind.GRID_METER, DeviceKind.PV}),
                fallback=(
                    FallbackMode.SAFE_HOLD
                    if kind in {DeviceKind.GRID_METER, DeviceKind.PV}
                    else FallbackMode.NO_AUTOMATION
                ),
                confidence=0.8,
                source_entities=(entity_id,),
                automations_allowed=kind in {DeviceKind.GRID_METER, DeviceKind.PV},
            )

        add(CONF_METER_ENTITY, DeviceKind.GRID_METER, {Capability.MEASURE_POWER}, "Netz-Leistung")
        add(CONF_METER_IMPORT_ENTITY, DeviceKind.GRID_METER, {Capability.MEASURE_POWER}, "Netz-Bezug")
        add(CONF_METER_EXPORT_ENTITY, DeviceKind.GRID_METER, {Capability.MEASURE_POWER}, "Netz-Einspeisung")
        add(CONF_PV_ENTITY, DeviceKind.PV, {Capability.MEASURE_POWER}, "PV-Erzeugung")
        add(CONF_LOAD_ENTITY, DeviceKind.LOAD, {Capability.MEASURE_POWER}, "Hausverbrauch")
        add(
            CONF_BATTERY_ENTITY,
            DeviceKind.BATTERY,
            {Capability.MEASURE_POWER, Capability.MEASURE_SOC},
            "Batterie",
        )
        add(CONF_WEATHER_ENTITY, DeviceKind.UNKNOWN, {Capability.READ_WEATHER}, "Wetter")
        add(CONF_CALENDAR_ENTITY, DeviceKind.UNKNOWN, {Capability.READ_CALENDAR}, "Kalender")
        add(CONF_PRICE_ENTITY, DeviceKind.UNKNOWN, {Capability.MEASURE_PRICE}, "Strompreis")

        for device in self.devices.values():
            capabilities = {
                Capability(value)
                for value in device.get("capabilities", [])
                if value in Capability._value2member_map_
            }
            limits = DeviceLimits(**device.get("limits", {}))
            try:
                kind = DeviceKind(device.get("kind", DeviceKind.UNKNOWN.value))
            except ValueError:
                kind = DeviceKind.UNKNOWN
            try:
                fallback = FallbackMode(device.get("fallback", "no_automation"))
            except ValueError:
                fallback = FallbackMode.NO_AUTOMATION
            device_id = str(device.get("device_id", ""))
            profiles[device_id] = DeviceProfile(
                device_id=device_id,
                name=str(device.get("name", device_id)),
                kind=kind,
                capabilities=capabilities,
                limits=limits,
                fallback=fallback,
                confidence=0.95,
                manually_configured=True,
                source_entities=(str(device.get("entity_id", "")),),
                nickname=str(device.get("nickname") or "") or None,
                priority=int(device.get("priority", 50)),
                automations_allowed=bool(device.get("automations_allowed", False)),
            )
        return profiles

    def _device_snapshots(
        self,
        profiles: dict[str, DeviceProfile],
        readings: dict[str, dict[str, Any]],
        now: datetime,
    ) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        graph_limit = max(float(self.settings.get("grid_import_limit_w") or 0.0), 0.0)
        for profile in profiles.values():
            entity_id = profile.source_entities[0] if profile.source_entities else None
            value, unit, fresh, age = self._reading(entity_id, now)
            valid = value is not None and fresh
            decision = resolve_fallback(
                profile,
                reading_valid=valid,
                reading_fresh=fresh,
                limit_verified=profile.limits.verified or profile.manually_configured,
                manual_override=profile.device_id in self.manual_overrides,
                emergency_stop=bool(self.settings.get("emergency_stop")),
            )
            readings[profile.device_id] = {
                "value": value,
                "unit": unit,
                "age_seconds": None if age == float("inf") else round(age),
                "fresh": fresh,
            }
            snapshots.append(
                {
                    "device_id": profile.device_id,
                    "name": profile.nickname or profile.name,
                    "kind": profile.kind.value,
                    "area_name": profile.area_name,
                    "capabilities": sorted(capability.value for capability in profile.capabilities),
                    "controllable": profile.controllable,
                    "limits": asdict(profile.limits),
                    "fallback": decision.mode.value,
                    "automation_allowed": decision.automation_allowed,
                    "decision": {
                        "reason_code": decision.reason_code,
                        "message_de": decision.message_de,
                        "message_en": decision.message_en,
                        "severity": decision.severity.value,
                        "requires_user_action": decision.requires_user_action,
                    },
                    "warnings": limit_warnings(profile),
                    "reading": readings[profile.device_id],
                    "manually_configured": profile.manually_configured,
                    "priority": profile.priority,
                    "grid_headroom_w": max(graph_limit - (value or 0.0), 0.0) if graph_limit else None,
                }
            )
        snapshots.sort(key=lambda item: (item["priority"], item["name"]))
        return snapshots

    # ------------------------------------------------------------------
    # Forecast and planning
    # ------------------------------------------------------------------
    def _build_forecast(self, now: datetime) -> dict[str, Any]:
        history = [(timestamp, value / 1000.0) for timestamp, value in self._load_samples]
        profile = build_baseline(history) if history else build_baseline([])
        consumption = consumption_forecast(profile, start=now, end=now + timedelta(hours=24), step_minutes=60)
        solar = self._solar_forecast(now)
        total_solar = round(sum(point.expected_kwh for point in solar), 3)
        total_consumption = round(sum(point.expected_kwh for point in consumption), 3)
        confidence = 0.3 if not history else min(0.85, 0.4 + len(history) / 2000)
        return {
            "solar_kwh_next_24h": total_solar,
            "consumption_kwh_next_24h": total_consumption,
            "confidence": round(confidence, 3),
            "confidence_label": confidence_label(confidence),
            "solar": [point.as_dict() for point in solar],
            "consumption": [point.as_dict() for point in consumption],
            "weather": self._read_weather(),
        }

    def _solar_forecast(self, now: datetime) -> list[ForecastPoint]:
        peak_w = float(self.settings.get("pv_peak_w") or 0.0)
        if peak_w <= 0:
            peak_w = max((value for _, value in self._pv_samples), default=0.0)
        if peak_w <= 0:
            return []
        sun = self._state("sun.sun")
        sunrise = sunset = None
        if sun is not None:
            sunrise_raw = sun.attributes.get("next_rising")
            sunset_raw = sun.attributes.get("next_setting")
            sunrise = _parse_datetime(sunrise_raw)
            sunset = _parse_datetime(sunset_raw)
        if sunrise is None or sunset is None or sunset <= sunrise:
            return []
        weather = self._read_weather()
        cloud = weather.get("cloud_coverage_pct")
        efficiency = 1.0
        if cloud is not None:
            efficiency = max(1.0 - 0.65 * (float(cloud) / 100.0), 0.1)
        raw: list[SolarForecastInput] = []
        cursor = max(sunrise, now.replace(minute=0, second=0, microsecond=0))
        end = min(sunset, now + timedelta(hours=24))
        while cursor < end:
            slot_end = min(cursor + timedelta(hours=1), end)
            midpoint = cursor + (slot_end - cursor) / 2
            total_seconds = max((sunset - sunrise).total_seconds(), 1.0)
            phase = (midpoint - sunrise).total_seconds() / total_seconds
            shape = max(0.0, math.sin(math.pi * phase))
            kwh = peak_w / 1000.0 * shape * 1.0
            raw.append(
                SolarForecastInput(
                    start=cursor,
                    end=slot_end,
                    expected_kwh=kwh,
                    confidence=0.5,
                    source="sun_curve_estimate",
                )
            )
            cursor = slot_end
        return solar_forecast(raw, efficiency=efficiency)

    @staticmethod
    def _display_name(device: dict[str, Any]) -> str:
        """Return a human readable device name for the UI.

        Plans used to carry only entity ids, so the panel showed raw strings
        like ``sensor.wallbox_power`` as headings.
        """
        return str(device.get("nickname") or device.get("name") or device.get("device_id") or "")

    def _build_plans(self, now: datetime) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        chargers = [d for d in self.devices.values() if d.get("kind") == DeviceKind.EV_CHARGER.value]
        vehicles = [d for d in self.devices.values() if d.get("kind") == DeviceKind.EV.value]
        if not chargers:
            return plans
        solar_windows = self._solar_windows(now)
        departure = self._next_departure(now)
        for charger in chargers[:3]:
            vehicle = vehicles[0] if vehicles else None
            required = 0.0
            current_soc = None
            capacity = None
            target_soc = 80.0
            if vehicle is not None:
                current_soc = self._read_soc_for(vehicle.get("device_id", ""))
                limits = vehicle.get("limits") or {}
                capacity = safe_float(limits.get("battery_capacity_kwh"))
                target_soc = safe_float(vehicle.get("target_soc")) or 80.0
                computed, _error = energy_from_soc(
                    current_soc=current_soc,
                    target_soc=target_soc,
                    capacity_kwh=capacity,
                )
                if computed is not None:
                    required = computed
            if vehicle is not None and required <= 0:
                # A car without an available state of charge can still be shown,
                # but must never be charged automatically. The user decides.
                plans.append(
                    {
                        "vehicle_id": str(vehicle.get("device_id")),
                        "wallbox_id": str(charger.get("device_id")),
                        "vehicle_name": self._display_name(vehicle),
                        "wallbox_name": self._display_name(charger),
                        "feasible": False,
                        "planned_energy_kwh": 0.0,
                        "solar_energy_kwh": 0.0,
                        "grid_energy_kwh": 0.0,
                        "slots": [],
                        "warnings": ["soc_unknown"],
                        "reasons_de": [
                            "Ladestand oder Kapazität ist unbekannt. Es wird nicht automatisch "
                            "geladen; bitte im Auto oder manuell ein Ziel vorgeben."
                        ],
                        "reasons_en": [
                            "State of charge or capacity is unknown. Charging will not start "
                            "automatically; set a target in the car or manually."
                        ],
                    }
                )
                continue
            if required <= 0:
                continue
            request = ChargingRequest(
                vehicle_id=str(vehicle.get("device_id") if vehicle else "unknown_vehicle"),
                wallbox_id=str(charger.get("device_id")),
                required_energy_kwh=required,
                departure=departure,
                target_soc=target_soc,
                current_soc=current_soc,
                battery_capacity_kwh=capacity,
                max_power_w=float((charger.get("limits") or {}).get("max_power_w") or 11_000.0),
                min_power_w=1_400.0,
                grid_charging_allowed=bool(self.settings.get("grid_charging_allowed", False)),
                prefer_solar=True,
            )
            engine = ConstraintEngine()
            engine.add_grid_limits(
                net_power_w=0.0,
                import_limit_w=float(self.settings.get("grid_import_limit_w") or 0.0),
                export_limit_w=float(self.settings.get("grid_export_limit_w") or 0.0),
            )
            engine.add_device_power(
                label=request.wallbox_id,
                max_power_w=request.max_power_w,
            )
            plan = plan_charging(request, now=now, solar_windows=solar_windows, engine=engine)
            payload = plan.as_dict()
            payload["vehicle_name"] = self._display_name(vehicle) if vehicle else ""
            payload["wallbox_name"] = self._display_name(charger)
            plans.append(payload)
        return plans

    def _solar_windows(self, now: datetime) -> list[SolarWindow]:
        return [
            SolarWindow(
                start=point.start,
                end=point.end,
                surplus_power_w=point.expected_kwh * 1000.0,
                confidence=point.confidence,
            )
            for point in self._solar_forecast(now)
            if point.expected_kwh > 0
        ]

    def _read_soc_for(self, device_id: str) -> float | None:
        state = self._state(device_id)
        if state is None:
            return None
        value = safe_float(state.attributes.get("battery_level"))
        return value if value is not None else safe_float(state.state)

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    def _evaluate_security(
        self,
        devices: list[dict[str, Any]],
        grid: Any,
        balance: Any,
        constraints: ConstraintEngine,
        now: datetime,
    ) -> SecurityReport:
        health: dict[str, ModuleHealth] = {}
        for spec in MODULE_SPECS:
            enabled = spec.module_id in self.enabled
            contract = ModuleContract(
                inputs=set(spec.requires),
                outputs=set(spec.provides),
            )
            observed_inputs = {
                dependency
                for dependency in spec.requires
                if dependency in self.enabled or dependency == CORE_MODULE_ID
            }
            status = HealthStatus.READY
            error_de = error_en = None
            if spec.module_id == "forecast_learning" and not self.entry.options.get(CONF_PV_ENTITY):
                status = HealthStatus.DEGRADED
                error_de = "Keine PV-Leistungsentität ausgewählt."
                error_en = "No PV power entity selected."
            if spec.module_id == "mobility_calendar" and not self.entry.options.get(CONF_CALENDAR_ENTITY):
                status = HealthStatus.DEGRADED
                error_de = "Kein Kalender ausgewählt; sichere Ersatzplanung aktiv."
                error_en = "No calendar selected; safe fallback planning active."
            if spec.module_id == "ev_wallbox_link" and not any(
                device["kind"] == DeviceKind.EV_CHARGER.value for device in devices
            ):
                status = HealthStatus.DEGRADED
                error_de = "Noch keine Wallbox eingerichtet."
                error_en = "No wallbox configured yet."
            health[spec.module_id] = ModuleHealth(
                module_id=spec.module_id,
                status=status if enabled else HealthStatus.DISABLED,
                last_heartbeat=now,
                last_error_de=error_de,
                last_error_en=error_en,
                contract=contract,
                observed_inputs=observed_inputs,
                observed_outputs=set(spec.provides),
                enabled=enabled,
            )
            if spec.module_id == "ev_wallbox_link":
                health[spec.module_id].contract.inputs.add("vehicle_link")
                health[spec.module_id].contract.outputs.add("vehicle_link")
        reading_ages = {
            device["name"]: float(device["reading"]["age_seconds"] or 999999)
            for device in devices
            if device["reading"]["age_seconds"] is not None
        }
        hard = [constraint.label for constraint in constraints.hard_violations()]
        return self.terminal.evaluate(
            modules=health,
            now=now,
            emergency_stop=bool(self.settings.get("emergency_stop")),
            reading_ages=reading_ages,
            hard_violations=hard,
            balance_ok=balance.balanced,
            privacy_mode=str(self.privacy.get("mode", "local_only")),
            ai_enabled=bool(self.ai.get("enabled")),
        )

    # ------------------------------------------------------------------
    # AI and privacy
    # ------------------------------------------------------------------
    def prepare_ai_preview(self) -> dict[str, Any]:
        """Prepare the preview that the user must confirm before sending."""
        now = dt_util.utcnow()
        report = self.terminal.evaluate(
            modules={},
            now=now,
            emergency_stop=bool(self.settings.get("emergency_stop")),
        )
        device_context = [
            {
                "id": device["device_id"],
                "kind": device["kind"],
                "capabilities": device.get("capabilities", []),
                "automation_allowed": device.get("automation_allowed", False),
                "metrics": {
                    "power_w": (device.get("reading") or {}).get("value"),
                    "age_seconds": (device.get("reading") or {}).get("age_seconds"),
                },
                "error_codes": list(device.get("warnings", [])),
                "module": "core",
            }
            for device in (self.last_snapshot or {}).get("devices", [])
        ]
        summary = (self.last_snapshot or {}).get("summary", {})
        request = self.advisor.prepare(
            vault=self.alias_vault,
            provider_id=str(self.ai.get("provider_id", "local_rules")),
            modules=device_context,
            report=report,
            summary=summary,
            locale=str(self.settings.get("language", "de")),
        )
        self._ai_preview = request
        return request.preview.as_dict()

    async def async_request_ai_report(
        self,
        *,
        provider_id: str,
        user_confirmed: bool,
        transport_factory: Any | None = None,
    ) -> dict[str, Any]:
        """Run an advisory report; never returns executable commands."""
        now = dt_util.utcnow()
        if self._ai_preview is None:
            self.prepare_ai_preview()
        if self._ai_preview is None:
            return {"ok": False, "error": "preview_failed"}
        if provider_id != "local_rules" and transport_factory is not None:
            provider = transport_factory(provider_id)
            self.advisor.providers[provider_id] = provider
        report = await self.advisor.analyse(
            self._ai_preview,
            now=now,
            provider_id=provider_id,
            user_confirmed=user_confirmed,
        )
        self.last_ai_report = report
        self.audit.record(
            kind=AuditKind.AI,
            message_de=f"KI-Bericht über {provider_id} erstellt.",
            message_en=f"AI report created via {provider_id}.",
            now=now,
            reason="user",
            context={"external": report.external_data_sent},
        )
        return {"ok": True, "report": report.as_dict()}

    def _ai_state(self) -> dict[str, Any]:
        return {
            "provider_id": self.ai.get("provider_id", "local_rules"),
            "enabled": bool(self.ai.get("enabled")),
            "api_key_set": bool(self.ai.get("api_key_set")),
            "report_interval": self.ai.get("report_interval", DEFAULT_REPORT_INTERVAL),
            "last_report": self.last_ai_report.as_dict() if self.last_ai_report else None,
            "ai_can_control": False,
        }

    def _privacy_state(self) -> dict[str, Any]:
        mode = str(self.privacy.get("mode", "local_only"))
        external = mode != PrivacyMode.LOCAL_ONLY.value and bool(self.ai.get("enabled"))
        return {
            "mode": mode,
            "external_active": external,
            "indicator": "red" if external else "green",
            "label_de": (
                "ROT: Externe KI aktiv – pseudonymisierte Daten können gesendet werden."
                if external
                else "GRÜN: Lokal – keine externe KI-Datenübertragung."
            ),
            "label_en": (
                "RED: External AI active – pseudonymized data may be sent."
                if external
                else "GREEN: Local – no external AI data transfer."
            ),
            "settings": {key: value for key, value in self.privacy.items() if key != "api_key"},
        }

    def _calibration_state(self) -> dict[str, Any]:
        run = self.calibration_run
        if run is None:
            return {"active": False}
        return {
            "active": run.state is not CalibrationState.IDLE,
            "device_id": run.device_id,
            "entity_id": run.entity_id,
            "state": run.state.value,
            "step": run.step,
            "used_energy_kwh": round(run.used_energy_kwh, 4),
            "summary_de": run.summary_de(),
            "summary_en": run.summary_en(),
            "log": list(run.log[-20:]),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _apply_privacy_settings(self) -> None:
        self.advisor.settings = PrivacySettings(
            mode=PrivacyMode(str(self.privacy.get("mode", "local_only"))),
            include_numbers=bool(self.privacy.get("include_numbers", True)),
            include_error_codes=bool(self.privacy.get("include_error_codes", True)),
            include_weather=bool(self.privacy.get("include_weather", True)),
            include_energy_history=bool(self.privacy.get("include_energy_history", False)),
            include_calendar_presence_only=bool(self.privacy.get("include_calendar_presence_only", False)),
            include_module_versions=bool(self.privacy.get("include_module_versions", True)),
            rotate_alias_every_report=bool(self.privacy.get("rotate_alias_every_report", True)),
            allow_external_provider=bool(self.privacy.get("allow_external_provider", False)),
            preview_required=bool(self.privacy.get("preview_required", True)),
        )

    def _build_terminal_config(self) -> TerminalConfig:
        return TerminalConfig(
            level=SecurityLevel(str(self.terminal_config.get("level", "observe"))),
            reaction=ReactionSpeed(str(self.terminal_config.get("reaction", "30s"))),
            repeat_minutes=int(self.terminal_config.get("repeat_minutes", 15)),
            repeat_until_resolved=bool(self.terminal_config.get("repeat_until_resolved", True)),
            max_repeats=int(self.terminal_config.get("max_repeats", 6)),
            allow_module_pause=bool(self.terminal_config.get("allow_module_pause", False)),
            allow_safe_stop=bool(self.terminal_config.get("allow_safe_stop", False)),
            allow_emergency_stop=bool(self.terminal_config.get("allow_emergency_stop", False)),
        )

    def entity_candidates(self) -> list[dict[str, Any]]:
        """Return automatic discovery candidates for the UI."""
        descriptors: list[EntityDescriptor] = []
        for state in self.hass.states.async_all():
            attributes = state.attributes
            descriptors.append(
                EntityDescriptor(
                    entity_id=state.entity_id,
                    domain=state.domain,
                    name=attributes.get("friendly_name", state.entity_id),
                    unit=attributes.get("unit_of_measurement"),
                    device_class=attributes.get("device_class"),
                    state_class=attributes.get("state_class"),
                    state=state.state,
                    available=state.state not in {"unknown", "unavailable"},
                    area_name=attributes.get("area_name"),
                    attributes=dict(attributes),
                    last_changed=state.last_changed,
                )
            )
        known = set(self.entry.options.values()) | set(self.devices)
        return [
            {
                "entity_id": candidate.entity_id,
                "name": candidate.name,
                "kind": candidate.kind.value,
                "score": candidate.score,
                "capabilities": sorted(capability.value for capability in candidate.capabilities),
                "reasons": list(candidate.reasons),
                "warnings": list(candidate.warnings),
                "manual": candidate.manual,
            }
            for candidate in discover_candidates(descriptors, known_entities=known)[:80]
        ]


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
