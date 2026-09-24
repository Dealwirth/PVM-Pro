"""Contract tests for the final device command gate."""

from __future__ import annotations

import unittest

from custom_components.pv_manager.core.execution import evaluate_manual_action
from custom_components.pv_manager.core.limits import ConstraintEngine


def engine(limit_w: float = 5000.0, current_w: float = 0.0) -> ConstraintEngine:
    result = ConstraintEngine()
    result.add_grid_limits(net_power_w=current_w, import_limit_w=limit_w, export_limit_w=0.0)
    return result


class ManualActionTests(unittest.TestCase):
    def test_turn_off_is_always_a_safe_stop(self) -> None:
        result = evaluate_manual_action(
            controllable=True,
            desired_on=False,
            emergency_stop=True,
            automation_allowed=False,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason_code, "safe_stop")

    def test_emergency_stop_blocks_turn_on(self) -> None:
        result = evaluate_manual_action(
            controllable=True,
            desired_on=True,
            emergency_stop=True,
            automation_allowed=True,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "emergency_stop")

    def test_unknown_actuator_blocks(self) -> None:
        result = evaluate_manual_action(
            controllable=False,
            desired_on=True,
            emergency_stop=False,
            automation_allowed=True,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "not_controllable")

    def test_unverified_fallback_blocks_turn_on(self) -> None:
        result = evaluate_manual_action(
            controllable=True,
            desired_on=True,
            emergency_stop=False,
            automation_allowed=False,
            fallback_reason="limits_unverified",
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "limits_unverified")

    def test_hard_limit_blocks_turn_on(self) -> None:
        result = evaluate_manual_action(
            controllable=True,
            desired_on=True,
            emergency_stop=False,
            automation_allowed=True,
            requested_power_w=4000,
            engine=engine(limit_w=1000, current_w=0),
        )
        self.assertTrue(result.allowed)
        self.assertTrue(result.clamped)
        self.assertEqual(result.allowed_power_w, 1000)

    def test_existing_violation_blocks_turn_on(self) -> None:
        result = evaluate_manual_action(
            controllable=True,
            desired_on=True,
            emergency_stop=False,
            automation_allowed=True,
            requested_power_w=2000,
            engine=engine(limit_w=5000, current_w=6000),
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "grid_import")

    def test_happy_path(self) -> None:
        result = evaluate_manual_action(
            controllable=True,
            desired_on=True,
            emergency_stop=False,
            automation_allowed=True,
            requested_power_w=2000,
            engine=engine(limit_w=11000),
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason_code, "ok")
        self.assertEqual(result.allowed_power_w, 2000)
        self.assertFalse(result.clamped)


if __name__ == "__main__":
    unittest.main()
