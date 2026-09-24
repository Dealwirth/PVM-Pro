"""Contract tests for unit and sign normalization."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from custom_components.pv_manager.core.normalize import (
    compute_balance,
    integrate_energy_kwh,
    is_stale,
    normalize_energy,
    normalize_grid_sample,
    normalize_power,
    parse_grid_mode,
    safe_float,
)
from custom_components.pv_manager.core.types import SignConvention

UTC = UTC


class NormalizePowerTests(unittest.TestCase):
    def test_power_units(self) -> None:
        self.assertEqual(normalize_power(1.5, "kW"), 1500.0)
        self.assertEqual(normalize_power(1500, "W"), 1500.0)
        self.assertAlmostEqual(normalize_power(1, "MW") or 0, 1_000_000.0)

    def test_energy_units(self) -> None:
        self.assertEqual(normalize_energy(1000, "Wh"), 1.0)
        self.assertEqual(normalize_energy(2, "kWh"), 2.0)
        self.assertEqual(normalize_energy(1, "MWh"), 1000.0)

    def test_unknown_unit_is_safe(self) -> None:
        self.assertIsNone(normalize_power(5, "furlongs"))
        self.assertIsNone(normalize_energy(5, "buckets"))

    def test_safe_float(self) -> None:
        self.assertEqual(safe_float("12.5"), 12.5)
        self.assertEqual(safe_float("12,5"), 12.5)
        self.assertIsNone(safe_float("unavailable"))
        self.assertIsNone(safe_float(None))
        self.assertIsNone(safe_float(True))
        self.assertIsNone(safe_float(float("nan")))


class GridSignTests(unittest.TestCase):
    def test_signed_net_positive_is_import(self) -> None:
        sample = normalize_grid_sample(combined_value=2000, unit="W", convention="signed_net")
        self.assertEqual(sample.import_power_w, 2000)
        self.assertEqual(sample.export_power_w, 0)

    def test_signed_net_negative_is_export(self) -> None:
        sample = normalize_grid_sample(combined_value=-3000, unit="W", convention="signed_net")
        self.assertEqual(sample.import_power_w, 0)
        self.assertEqual(sample.export_power_w, 3000)
        self.assertEqual(sample.net_power_w, -3000)

    def test_export_positive_is_inverted(self) -> None:
        sample = normalize_grid_sample(combined_value=1500, unit="W", convention="export_positive")
        self.assertEqual(sample.import_power_w, 0)
        self.assertEqual(sample.export_power_w, 1500)

    def test_unknown_sign_is_not_guessed(self) -> None:
        sample = normalize_grid_sample(combined_value=1200, unit="W", convention="unknown")
        self.assertAlmostEqual(sample.confidence, 0.5)
        self.assertEqual(sample.warning, "unknown_sign_convention")

    def test_separate_values_are_never_both_assumed_clean(self) -> None:
        sample = normalize_grid_sample(
            import_value=1000,
            export_value=2500,
            unit="W",
            convention="separate",
        )
        self.assertEqual(sample.net_power_w, -1500)
        self.assertEqual(sample.warning, "import_and_export_at_once")
        self.assertLess(sample.confidence, 1.0)

    def test_separate_single_direction_is_confident(self) -> None:
        sample = normalize_grid_sample(
            import_value=500,
            export_value=0,
            unit="W",
            convention="separate",
        )
        self.assertEqual(sample.import_power_w, 500)
        self.assertIsNone(sample.warning)
        self.assertAlmostEqual(sample.confidence, 1.0)

    def test_import_only_marks_export_unknown(self) -> None:
        sample = normalize_grid_sample(import_value=800, unit="W", convention="import_only")
        self.assertEqual(sample.import_power_w, 800)
        self.assertEqual(sample.warning, "export_unknown_import_only")

    def test_negative_import_only_is_rejected(self) -> None:
        sample = normalize_grid_sample(import_value=-200, unit="W", convention="import_only")
        self.assertEqual(sample.warning, "import_only_negative")
        self.assertAlmostEqual(sample.confidence, 0.2)

    def test_missing_data(self) -> None:
        sample = normalize_grid_sample(unit="W", convention="signed_net")
        self.assertIsNone(sample.import_power_w)
        self.assertEqual(sample.warning, "no_grid_data")

    def test_parse_grid_mode(self) -> None:
        self.assertIs(parse_grid_mode("signed"), SignConvention.SIGNED_NET)
        self.assertIs(parse_grid_mode("Nur_Bezug"), SignConvention.IMPORT_ONLY)
        self.assertIs(parse_grid_mode(None), SignConvention.UNKNOWN)


class BalanceTests(unittest.TestCase):
    def test_balance_with_pv_and_grid(self) -> None:
        balance = compute_balance(
            pv_w=5000,
            grid_import_w=0,
            grid_export_w=1500,
            battery_charge_w=1000,
            measured_load_w=2500,
        )
        self.assertAlmostEqual(balance.computed_load_w, 2500)
        self.assertTrue(balance.balanced)

    def test_balance_detects_implausible_readings(self) -> None:
        balance = compute_balance(
            pv_w=1000,
            grid_import_w=0,
            measured_load_w=5000,
        )
        self.assertFalse(balance.balanced)
        self.assertIn("load_balance_deviation", balance.warnings)

    def test_simultaneous_import_and_export_is_flagged(self) -> None:
        balance = compute_balance(grid_import_w=500, grid_export_w=500)
        self.assertFalse(balance.balanced)

    def test_integration(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        samples = [
            (start, 0.0),
            (start + timedelta(hours=1), 1000.0),
            (start + timedelta(hours=2), 1000.0),
            (start + timedelta(hours=3), 0.0),
        ]
        # Trapezoid: 0.5 + 1.0 + 0.5 = 2.0 kWh
        self.assertAlmostEqual(integrate_energy_kwh(samples), 2.0)

    def test_stale(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        self.assertTrue(is_stale(None, now, timedelta(minutes=5)))
        self.assertTrue(is_stale(now - timedelta(minutes=6), now, timedelta(minutes=5)))
        self.assertFalse(is_stale(now - timedelta(minutes=4), now, timedelta(minutes=5)))


if __name__ == "__main__":
    unittest.main()
