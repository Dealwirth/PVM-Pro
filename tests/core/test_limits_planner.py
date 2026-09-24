"""Contract tests for limits and the charging planner."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from custom_components.pv_manager.core.limits import ConstraintEngine, amps_to_watts, watts_to_amps
from custom_components.pv_manager.core.planner import (
    ChargingRequest,
    SolarWindow,
    energy_from_soc,
    plan_charging,
)

UTC = UTC
NOW = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def engine(*, import_limit_w: float = 11_000.0, device_max_w: float = 11_000.0) -> ConstraintEngine:
    result = ConstraintEngine()
    result.add_grid_limits(net_power_w=0.0, import_limit_w=import_limit_w, export_limit_w=0.0)
    result.add_device_power(label="wallbox", max_power_w=device_max_w)
    return result


class LimitTests(unittest.TestCase):
    def test_clamp_reduces_to_grid_headroom(self) -> None:
        clamp = engine(import_limit_w=5000).clamp(11_000)
        self.assertTrue(clamp.reduced)
        self.assertAlmostEqual(clamp.allowed_w, 5000)

    def test_existing_violation_blocks(self) -> None:
        constraint_engine = ConstraintEngine()
        constraint_engine.add_grid_limits(net_power_w=6000, import_limit_w=5000, export_limit_w=0)
        clamp = constraint_engine.clamp(2000)
        self.assertFalse(clamp.allowed)
        self.assertEqual(clamp.blocking_reason, "grid_import")

    def test_phase_headroom(self) -> None:
        constraint_engine = ConstraintEngine()
        constraint_engine.add_phase_limit(phase_current_a=10, phase_limit_a=16, phases=3)
        clamp = constraint_engine.clamp(11_000)
        self.assertAlmostEqual(clamp.allowed_w, 6 * 230 * 3)

    def test_current_conversion(self) -> None:
        self.assertAlmostEqual(amps_to_watts(16, phases=3), 16 * 230 * 3)
        self.assertAlmostEqual(watts_to_amps(16 * 230 * 3, phases=3), 16)

    def test_snapshot_serializable(self) -> None:
        data = engine().snapshot()
        self.assertTrue(data)
        self.assertIn("headroom", data[0])


class PlannerTests(unittest.TestCase):
    def request(self, **overrides) -> ChargingRequest:
        values = {
            "vehicle_id": "car-1",
            "wallbox_id": "wallbox-1",
            "required_energy_kwh": 20.0,
            "departure": NOW + timedelta(hours=12),
            "max_power_w": 11_000.0,
            "grid_charging_allowed": False,
        }
        values.update(overrides)
        return ChargingRequest(**values)

    def test_solar_can_cover_request(self) -> None:
        windows = [
            SolarWindow(start=NOW + timedelta(hours=1), end=NOW + timedelta(hours=6), surplus_power_w=11_000)
        ]
        plan = plan_charging(self.request(required_energy_kwh=10), now=NOW, solar_windows=windows)
        self.assertTrue(plan.feasible)
        self.assertAlmostEqual(plan.solar_energy_kwh, 10.0)
        self.assertEqual(plan.grid_energy_kwh, 0.0)

    def test_grid_not_allowed_blocks_when_solar_is_missing(self) -> None:
        plan = plan_charging(self.request(), now=NOW, solar_windows=[])
        self.assertFalse(plan.feasible)
        self.assertIn("grid_not_allowed", plan.warnings)
        self.assertEqual(plan.grid_energy_kwh, 0.0)

    def test_grid_allowed_fills_deficit(self) -> None:
        plan = plan_charging(
            self.request(grid_charging_allowed=True),
            now=NOW,
            solar_windows=[],
        )
        self.assertTrue(plan.feasible)
        self.assertAlmostEqual(plan.grid_energy_kwh, 20.0)

    def test_insufficient_time_never_schedules_past_departure(self) -> None:
        request = self.request(grid_charging_allowed=True, required_energy_kwh=30)
        plan = plan_charging(
            request,
            now=NOW,
            solar_windows=[],
            engine=engine(import_limit_w=1000),
        )
        # 30 kWh at 1 kW needs 30 hours which is impossible before departure.
        self.assertFalse(plan.feasible)
        self.assertIn("insufficient_time", plan.warnings)
        self.assertTrue(plan.slots)
        self.assertLessEqual(plan.slots[-1].power_w, 1000)
        self.assertLessEqual(plan.slots[-1].end, request.departure)
        self.assertLess(plan.planned_energy_kwh, 30.0)

    def test_unknown_departure_blocks(self) -> None:
        plan = plan_charging(self.request(departure=None), now=NOW)
        self.assertFalse(plan.feasible)
        self.assertIn("departure_unknown", plan.warnings)

    def test_departure_in_past_blocks(self) -> None:
        plan = plan_charging(self.request(departure=NOW - timedelta(minutes=1)), now=NOW)
        self.assertFalse(plan.feasible)
        self.assertIn("departure_in_past", plan.warnings)

    def test_deadline_too_close_blocks(self) -> None:
        plan = plan_charging(self.request(departure=NOW + timedelta(minutes=10)), now=NOW)
        self.assertFalse(plan.feasible)
        self.assertIn("deadline_too_close", plan.warnings)

    def test_high_price_blocks_grid(self) -> None:
        plan = plan_charging(
            self.request(grid_charging_allowed=True),
            now=NOW,
            grid_price_high=True,
        )
        self.assertFalse(plan.feasible)
        self.assertIn("high_price", plan.warnings)

    def test_energy_from_soc(self) -> None:
        energy, error = energy_from_soc(current_soc=40, target_soc=80, capacity_kwh=60)
        self.assertIsNone(error)
        self.assertAlmostEqual(energy or 0, 24.0)
        energy, error = energy_from_soc(current_soc=None, target_soc=80, capacity_kwh=60)
        self.assertIsNone(energy)
        self.assertEqual(error, "soc_or_capacity_unknown")

    def test_plan_serializable(self) -> None:
        plan = plan_charging(self.request(grid_charging_allowed=True), now=NOW)
        data = plan.as_dict()
        self.assertIn("slots", data)
        self.assertIn("reasons_de", data)


if __name__ == "__main__":
    unittest.main()
