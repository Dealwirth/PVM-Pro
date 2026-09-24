"""Contract tests for fail-safe fallback decisions."""

from __future__ import annotations

import unittest

from custom_components.pv_manager.core.fallback import (
    Severity,
    default_fallback_mode,
    limit_warnings,
    required_capabilities,
    resolve_fallback,
)
from custom_components.pv_manager.core.types import (
    Capability,
    DeviceKind,
    DeviceLimits,
    DeviceProfile,
    FallbackMode,
    SignConvention,
)


def profile(
    kind: DeviceKind = DeviceKind.EV_CHARGER,
    capabilities: set[Capability] | None = None,
    *,
    allowed: bool = True,
    verified: bool = True,
    max_power_w: float = 11_000.0,
) -> DeviceProfile:
    return DeviceProfile(
        device_id="device-1",
        name="Test",
        kind=kind,
        capabilities=capabilities
        if capabilities is not None
        else {Capability.SET_POWER, Capability.MEASURE_POWER},
        limits=DeviceLimits(max_power_w=max_power_w, verified=verified),
        fallback=FallbackMode.NO_AUTOMATION,
        automations_allowed=allowed,
    )


class FallbackTests(unittest.TestCase):
    def test_unknown_device_is_never_automated(self) -> None:
        decision = resolve_fallback(
            None,
            reading_valid=True,
            reading_fresh=True,
            limit_verified=True,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertEqual(decision.reason_code, "unknown_device")
        self.assertTrue(decision.requires_user_action)

    def test_missing_capability_blocks(self) -> None:
        decision = resolve_fallback(
            profile(capabilities={Capability.SWITCH}),
            reading_valid=True,
            reading_fresh=True,
            limit_verified=True,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertEqual(decision.reason_code, "missing_capability")

    def test_not_enabled_by_user_blocks(self) -> None:
        decision = resolve_fallback(
            profile(allowed=False),
            reading_valid=True,
            reading_fresh=True,
            limit_verified=True,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertEqual(decision.reason_code, "not_enabled_by_user")

    def test_stale_reading_pauses(self) -> None:
        decision = resolve_fallback(
            profile(),
            reading_valid=True,
            reading_fresh=False,
            limit_verified=True,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertEqual(decision.reason_code, "stale_reading")
        self.assertEqual(decision.severity, Severity.WARNING)

    def test_unverified_limits_pause(self) -> None:
        decision = resolve_fallback(
            profile(verified=False),
            reading_valid=True,
            reading_fresh=True,
            limit_verified=False,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertEqual(decision.reason_code, "limits_unverified")

    def test_imbalance_pauses(self) -> None:
        decision = resolve_fallback(
            profile(),
            reading_valid=True,
            reading_fresh=True,
            limit_verified=True,
            balance_ok=False,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertEqual(decision.reason_code, "energy_balance_unconfirmed")

    def test_manual_override_is_allowed_but_not_automated(self) -> None:
        decision = resolve_fallback(
            profile(),
            reading_valid=True,
            reading_fresh=True,
            limit_verified=True,
            manual_override=True,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertTrue(decision.safe_command_allowed)

    def test_emergency_stop_wins(self) -> None:
        decision = resolve_fallback(
            profile(),
            reading_valid=True,
            reading_fresh=True,
            limit_verified=True,
            emergency_stop=True,
        )
        self.assertFalse(decision.automation_allowed)
        self.assertEqual(decision.severity, Severity.CRITICAL)

    def test_happy_path(self) -> None:
        decision = resolve_fallback(
            profile(),
            reading_valid=True,
            reading_fresh=True,
            limit_verified=True,
        )
        self.assertTrue(decision.automation_allowed)
        self.assertEqual(decision.reason_code, "ok")

    def test_default_modes_are_safe(self) -> None:
        self.assertEqual(default_fallback_mode(DeviceKind.EV), FallbackMode.NO_AUTOMATION)
        self.assertEqual(default_fallback_mode(DeviceKind.GRID_METER), FallbackMode.SAFE_HOLD)

    def test_required_capabilities(self) -> None:
        self.assertIn(Capability.MEASURE_SOC, required_capabilities(DeviceKind.BATTERY))
        self.assertIn(Capability.SET_POWER, required_capabilities(DeviceKind.EV_CHARGER))

    def test_limit_warnings(self) -> None:
        incomplete = profile(verified=False, max_power_w=0)
        warnings = limit_warnings(incomplete)
        self.assertIn("limits_not_verified", warnings)
        self.assertIn("max_power_missing", warnings)
        grid = DeviceProfile(
            device_id="grid",
            name="Grid",
            kind=DeviceKind.GRID_METER,
            capabilities={Capability.MEASURE_POWER},
            sign_convention=SignConvention.UNKNOWN,
            limits=DeviceLimits(verified=True, max_power_w=100),
        )
        self.assertIn("grid_sign_unknown", limit_warnings(grid))


if __name__ == "__main__":
    unittest.main()
