"""Contract tests for discovery and the internal module store."""

from __future__ import annotations

import unittest

from custom_components.pv_manager.core.discovery import (
    cap_control_without_measure,
    capabilities_for,
    discover_candidates,
    guess_kind,
)
from custom_components.pv_manager.core.modules import (
    CORE_MODULE_ID,
    MODULE_SPECS,
    MODULES_BY_ID,
    default_enabled_modules,
    dependents_of,
    resolve_dependencies,
    store_cards,
)
from custom_components.pv_manager.core.types import Capability, DeviceKind, EntityDescriptor


def entity(**overrides) -> EntityDescriptor:
    values = {
        "entity_id": "sensor.test",
        "domain": "sensor",
        "name": "Test",
    }
    values.update(overrides)
    return EntityDescriptor(**values)


class CapabilityTests(unittest.TestCase):
    def test_power_sensor(self) -> None:
        caps = capabilities_for(entity(unit="W", device_class="power"))
        self.assertIn(Capability.MEASURE_POWER, caps.capabilities)

    def test_energy_sensor(self) -> None:
        caps = capabilities_for(entity(unit="kWh", device_class="energy"))
        self.assertIn(Capability.MEASURE_ENERGY, caps.capabilities)

    def test_switch_is_actuator(self) -> None:
        caps = capabilities_for(entity(entity_id="switch.pool", domain="switch"))
        self.assertIn(Capability.SWITCH, caps.capabilities)

    def test_climate_can_set_temperature(self) -> None:
        caps = capabilities_for(entity(entity_id="climate.heat", domain="climate"))
        self.assertIn(Capability.SET_TEMPERATURE, caps.capabilities)

    def test_presence_domain(self) -> None:
        caps = capabilities_for(entity(entity_id="person.alex", domain="person"))
        self.assertIn(Capability.MEASURE_PRESENCE, caps.capabilities)

    def test_calendar_domain(self) -> None:
        caps = capabilities_for(entity(entity_id="calendar.work", domain="calendar"))
        self.assertIn(Capability.READ_CALENDAR, caps.capabilities)

    def test_control_without_measurement_is_flagged(self) -> None:
        self.assertTrue(cap_control_without_measure({Capability.SWITCH}))
        self.assertFalse(cap_control_without_measure({Capability.SWITCH, Capability.MEASURE_POWER}))


class KindGuessTests(unittest.TestCase):
    def test_grid_meter(self) -> None:
        kind, score, reasons = guess_kind(
            entity(entity_id="sensor.grid_power", unit="W", device_class="power")
        )
        self.assertIs(kind, DeviceKind.GRID_METER)
        self.assertGreater(score, 0.3)

    def test_pv(self) -> None:
        kind, _, _ = guess_kind(entity(entity_id="sensor.pv_generation", unit="W", device_class="power"))
        self.assertIs(kind, DeviceKind.PV)

    def test_wallbox(self) -> None:
        kind, _, _ = guess_kind(entity(entity_id="sensor.garage_wallbox_power", unit="W"))
        self.assertIs(kind, DeviceKind.EV_CHARGER)

    def test_heat_pump(self) -> None:
        kind, _, _ = guess_kind(entity(entity_id="sensor.waermepumpe_leistung", unit="W"))
        self.assertIs(kind, DeviceKind.HEAT_PUMP)

    def test_plain_power_is_load(self) -> None:
        kind, _, _ = guess_kind(entity(entity_id="sensor.random_power", device_class="power", unit="W"))
        self.assertIs(kind, DeviceKind.LOAD)


class DiscoverTests(unittest.TestCase):
    def test_returns_ranked_candidates(self) -> None:
        entities = [
            entity(entity_id="sensor.pv_power", name="PV Power", unit="W", device_class="power"),
            entity(entity_id="sensor.grid_power", name="Grid Power", unit="W", device_class="power"),
            entity(
                entity_id="sensor.weather_temp",
                name="Temperature",
                unit="°C",
                device_class="temperature",
            ),
        ]
        candidates = discover_candidates(entities)
        ids = [candidate.entity_id for candidate in candidates]
        self.assertIn("sensor.pv_power", ids)
        self.assertIn("sensor.grid_power", ids)
        self.assertNotIn("sensor.weather_temp", ids)

    def test_known_entities_are_excluded(self) -> None:
        candidates = discover_candidates(
            [entity(entity_id="sensor.pv_power", unit="W", device_class="power")],
            known_entities={"sensor.pv_power"},
        )
        self.assertEqual(candidates, [])

    def test_unavailable_entities_are_manual(self) -> None:
        candidates = discover_candidates(
            [entity(entity_id="sensor.pv_power", unit="W", device_class="power", available=False)]
        )
        self.assertTrue(candidates)
        self.assertTrue(candidates[0].manual)
        self.assertIn("offline", candidates[0].warnings)

    def test_control_without_measure_warning(self) -> None:
        candidates = discover_candidates([entity(entity_id="switch.pool_pump", domain="switch")])
        self.assertTrue(candidates)
        self.assertIn("control_without_measurement", candidates[0].warnings)


class ModuleStoreTests(unittest.TestCase):
    def test_exactly_15_modules(self) -> None:
        self.assertEqual(len(MODULE_SPECS), 15)

    def test_unique_ids(self) -> None:
        ids = [spec.module_id for spec in MODULE_SPECS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_core_is_default_and_mandatory(self) -> None:
        self.assertIn(CORE_MODULE_ID, default_enabled_modules())
        self.assertIn(CORE_MODULE_ID, MODULES_BY_ID)
        self.assertFalse(MODULES_BY_ID[CORE_MODULE_ID].optional)

    def test_all_modules_have_bilingual_text(self) -> None:
        for spec in MODULE_SPECS:
            self.assertTrue(spec.summary_de, spec.module_id)
            self.assertTrue(spec.summary_en, spec.module_id)
            self.assertTrue(spec.name_de, spec.module_id)
            self.assertTrue(spec.name_en, spec.module_id)

    def test_security_terminal_exists(self) -> None:
        terminal = MODULES_BY_ID["security_terminal"]
        self.assertEqual(terminal.safety_level, "high")
        self.assertIn("ai_advice", terminal.provides)

    def test_dependency_resolution(self) -> None:
        resolved = resolve_dependencies({CORE_MODULE_ID}, module_id="what_if")
        self.assertIn("forecast_learning", resolved)
        self.assertIn("what_if", resolved)

    def test_dependents(self) -> None:
        enabled = {"core", "forecast_learning", "what_if", "energy_habits"}
        self.assertIn("what_if", dependents_of("forecast_learning", enabled))

    def test_store_cards_serializable(self) -> None:
        cards = store_cards({"core"})
        self.assertEqual(len(cards), 15)
        self.assertTrue(cards[0]["enabled"])
        self.assertIn("summary_de", cards[0])


if __name__ == "__main__":
    unittest.main()
