"""Fail-safe fallback rules.

PV Manager never continues an automatic action when the device state is
unknown, stale or contradictory. It stops the automation, not necessarily the
device, and explains the reason to the user in plain language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .types import Capability, DeviceKind, DeviceProfile, FallbackMode


class Severity(StrEnum):
    """Severity used for UI and notifications."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class FallbackDecision:
    """Result of the fail-safe evaluation."""

    automation_allowed: bool
    mode: FallbackMode
    reason_code: str
    message_de: str
    message_en: str
    severity: Severity
    requires_user_action: bool = False
    safe_command_allowed: bool = False


def default_fallback_mode(kind: DeviceKind) -> FallbackMode:
    """Return the safe default for a device type."""
    if kind in {DeviceKind.GRID_METER, DeviceKind.PV, DeviceKind.LOAD}:
        return FallbackMode.SAFE_HOLD
    return FallbackMode.NO_AUTOMATION


def required_capabilities(kind: DeviceKind) -> set[Capability]:
    """Capabilities that a device must provide before control is allowed."""
    if kind is DeviceKind.GRID_METER:
        return {Capability.MEASURE_POWER}
    if kind is DeviceKind.PV:
        return {Capability.MEASURE_POWER}
    if kind is DeviceKind.BATTERY:
        return {Capability.MEASURE_POWER, Capability.MEASURE_SOC}
    if kind in {DeviceKind.EV_CHARGER, DeviceKind.EV}:
        return {Capability.SET_POWER, Capability.MEASURE_POWER}
    if kind in {DeviceKind.HEAT_PUMP, DeviceKind.HOT_WATER}:
        return {Capability.MEASURE_POWER}
    if kind in {DeviceKind.FLEXIBLE_LOAD, DeviceKind.POOL, DeviceKind.VENTILATION}:
        return {Capability.SWITCH}
    return set()


def resolve_fallback(
    profile: DeviceProfile | None,
    *,
    reading_valid: bool,
    reading_fresh: bool,
    balance_ok: bool = True,
    limit_verified: bool = False,
    manual_override: bool = False,
    emergency_stop: bool = False,
) -> FallbackDecision:
    """Evaluate whether automation for one device may run.

    The order is deliberate: hard safety first, then data quality, then
    capability, then the user's own override.
    """
    if emergency_stop:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.SAFE_HOLD,
            reason_code="emergency_stop",
            message_de="Not-Aus ist aktiv. Automatische Aktionen sind gesperrt.",
            message_en="Emergency stop is active. Automatic actions are blocked.",
            severity=Severity.CRITICAL,
            safe_command_allowed=False,
        )

    if profile is None:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.MANUAL,
            reason_code="unknown_device",
            message_de="Gerät ist noch nicht geprüft. Es wird nur angezeigt, nicht gesteuert.",
            message_en="Device is not verified yet. It is displayed but not controlled.",
            severity=Severity.WARNING,
            requires_user_action=True,
        )

    missing = required_capabilities(profile.kind) - profile.capabilities
    if missing:
        names = ", ".join(sorted(capability.value for capability in missing))
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.NO_AUTOMATION,
            reason_code="missing_capability",
            message_de=f"Wichtige Funktion fehlt: {names}. Automatik ist gesperrt.",
            message_en=f"Required capability is missing: {names}. Automation is blocked.",
            severity=Severity.WARNING,
            requires_user_action=True,
        )

    if not profile.automations_allowed and not manual_override:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.MANUAL,
            reason_code="not_enabled_by_user",
            message_de="Automatik wurde für dieses Gerät noch nicht freigegeben.",
            message_en="Automation has not been enabled for this device yet.",
            severity=Severity.INFO,
            requires_user_action=True,
        )

    if manual_override:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.MANUAL,
            reason_code="manual_override",
            message_de="Manueller Modus aktiv. Der Nutzer hat die Kontrolle.",
            message_en="Manual mode is active. The user is in control.",
            severity=Severity.INFO,
            safe_command_allowed=True,
        )

    if not reading_valid:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.SAFE_HOLD,
            reason_code="invalid_reading",
            message_de="Messwert fehlt oder ist ungültig. Keine automatische Änderung.",
            message_en="Reading is missing or invalid. No automatic change.",
            severity=Severity.WARNING,
            requires_user_action=True,
        )

    if not reading_fresh:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.SAFE_HOLD,
            reason_code="stale_reading",
            message_de="Messwert ist veraltet. Automatik pausiert, bis Daten wieder frisch sind.",
            message_en="Reading is stale. Automation pauses until data is fresh again.",
            severity=Severity.WARNING,
            requires_user_action=True,
        )

    if not limit_verified:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.SAFE_HOLD,
            reason_code="limits_unverified",
            message_de="Sicherheitsgrenzen sind noch nicht geprüft. Automatik bleibt gesperrt.",
            message_en="Safety limits are not verified yet. Automation stays blocked.",
            severity=Severity.WARNING,
            requires_user_action=True,
        )

    if not balance_ok:
        return FallbackDecision(
            automation_allowed=False,
            mode=FallbackMode.SAFE_HOLD,
            reason_code="energy_balance_unconfirmed",
            message_de="Energiebilanz ist nicht plausibel. Automatik pausiert.",
            message_en="Energy balance is not plausible. Automation pauses.",
            severity=Severity.WARNING,
            requires_user_action=True,
        )

    return FallbackDecision(
        automation_allowed=True,
        mode=profile.fallback,
        reason_code="ok",
        message_de="Automatik ist freigegeben und alle Prüfungen sind bestanden.",
        message_en="Automation is enabled and all checks passed.",
        severity=Severity.INFO,
    )


def limit_warnings(profile: DeviceProfile) -> list[str]:
    """Return user-facing warnings about unverified boundaries."""
    warnings: list[str] = []
    limits = profile.limits
    if not limits.verified:
        warnings.append("limits_not_verified")
    if profile.controllable and limits.max_power_w <= 0:
        warnings.append("max_power_missing")
    if (
        profile.kind in {DeviceKind.HEAT_PUMP, DeviceKind.HOT_WATER}
        and limits.max_temperature_c <= limits.min_temperature_c
    ):
        warnings.append("comfort_range_missing")
    if profile.kind in {DeviceKind.BATTERY, DeviceKind.EV} and limits.max_soc <= limits.min_soc:
        warnings.append("soc_range_missing")
    if profile.kind is DeviceKind.GRID_METER and profile.sign_convention.value == "unknown":
        warnings.append("grid_sign_unknown")
    return warnings
