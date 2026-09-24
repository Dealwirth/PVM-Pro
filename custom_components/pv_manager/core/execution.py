"""Final safety gate in front of every device command.

No UI button, service, module or AI may call a Home Assistant service without
passing through this deterministic check.
"""

from __future__ import annotations

from dataclasses import dataclass

from .limits import ConstraintEngine


@dataclass(frozen=True, slots=True)
class ManualActionResult:
    """Result of the final command check."""

    allowed: bool
    reason_code: str
    message_de: str
    message_en: str
    allowed_power_w: float = 0.0
    clamped: bool = False

    @property
    def blocked(self) -> bool:
        """Return True when the command must not be executed."""
        return not self.allowed


def evaluate_manual_action(
    *,
    controllable: bool,
    desired_on: bool,
    emergency_stop: bool,
    automation_allowed: bool,
    requested_power_w: float = 0.0,
    engine: ConstraintEngine | None = None,
    fallback_reason: str = "ok",
) -> ManualActionResult:
    """Evaluate whether an explicit device command may be executed.

    Turning a device **off** is always allowed (safe stop). Turning it **on**
    requires a controllable device, no emergency stop, a positive automation
    decision and enough remaining headroom in the hard limits.
    """
    if not controllable:
        return ManualActionResult(
            allowed=False,
            reason_code="not_controllable",
            message_de="Das Gerät hat keinen erkannten Stellbefehl. Es kann nicht geschaltet werden.",
            message_en="No actuator was detected for this device. It cannot be switched.",
        )
    # Switching off is always a safe stop, even during a notification-worthy
    # emergency state. This prevents PV Manager from blocking a shutdown.
    if not desired_on:
        return ManualActionResult(
            allowed=True,
            reason_code="safe_stop",
            message_de="Ausschalten ist als sicherer Stopp erlaubt.",
            message_en="Switching off is allowed as a safe stop.",
        )
    if emergency_stop:
        return ManualActionResult(
            allowed=False,
            reason_code="emergency_stop",
            message_de="Not-Aus ist aktiv. Es werden keine Einschaltbefehle ausgeführt.",
            message_en="Emergency stop is active. No switch-on commands are executed.",
        )
    if not automation_allowed:
        return ManualActionResult(
            allowed=False,
            reason_code=fallback_reason,
            message_de="Die Sicherheitsprüfung erlaubt das Einschalten derzeit nicht.",
            message_en="The safety check does not allow switching on right now.",
        )
    if engine is not None:
        clamp = engine.clamp(requested_power_w)
        if not clamp.allowed:
            return ManualActionResult(
                allowed=False,
                reason_code=clamp.blocking_reason or "hard_limit",
                message_de=(
                    f"Eine harte Grenze verhindert das Einschalten: {clamp.blocking_reason or 'unbekannt'}."
                ),
                message_en=(f"A hard limit prevents switching on: {clamp.blocking_reason or 'unknown'}."),
            )
        return ManualActionResult(
            allowed=True,
            reason_code="ok",
            message_de="Einschalten ist innerhalb der Grenzen erlaubt.",
            message_en="Switching on is allowed within the limits.",
            allowed_power_w=clamp.allowed_w,
            clamped=clamp.reduced,
        )
    return ManualActionResult(
        allowed=True,
        reason_code="ok",
        message_de="Einschalten ist erlaubt.",
        message_en="Switching on is allowed.",
        allowed_power_w=requested_power_w,
    )
