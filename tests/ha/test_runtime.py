"""Tests for the Home Assistant facing glue in ``runtime.py``.

The core tests import only ``custom_components.pv_manager.core`` and therefore
never execute ``runtime.py`` - the class that reads entity state, applies the
safety gate, writes the audit log and persists settings. These tests close that
hole using the stand-ins in :mod:`tests.ha.ha_stubs`, so no Home Assistant
installation is required.

``ha_stubs.install()`` must run before the integration is imported, which is why
the imports below are not at the top of the file.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import timedelta

from tests.ha import ha_stubs

ha_stubs.install()

from custom_components.pv_manager.const import (  # noqa: E402
    CONF_METER_ENTITY,
    CONF_METER_MODE,
    CONF_PV_ENTITY,
    DEFAULT_STALE_AFTER_SECONDS,
    STORAGE_KEY,
)
from custom_components.pv_manager.core.modules import CORE_MODULE_ID  # noqa: E402
from custom_components.pv_manager.core.security import (  # noqa: E402
    FindingSeverity,
    RiskFinding,
)
from custom_components.pv_manager.runtime import PVManagerRuntime  # noqa: E402

ENTRY_ID = "test-entry"
STORED_KEY = STORAGE_KEY.format(entry_id=ENTRY_ID)

# The kinds the audit log uses for the paths under test.
KIND_ACTION = "action"
KIND_DECISION = "decision"


def run(coroutine):
    """Run one coroutine to completion."""
    return asyncio.run(coroutine)


def make_runtime(hass=None, **options):
    """Return a runtime wired to in-memory stand-ins."""
    hass = hass or ha_stubs.FakeHass()
    entry = ha_stubs.FakeConfigEntry(options=options, entry_id=ENTRY_ID)
    return PVManagerRuntime(hass, entry), hass


def register_device(runtime, device_id="switch.pool", **overrides):
    """Register one controllable device, safe by default exactly like the UI."""
    device = {
        "device_id": device_id,
        "entity_id": device_id,
        "name": "Poolpumpe",
        "kind": "flexible_load",
        "capabilities": ["switch", "measure_power"],
        "limits": {"verified": False, "max_power_w": 0},
        "fallback": "no_automation",
        "automations_allowed": False,
    }
    device.update(overrides)
    return runtime.register_device(device)


def give_reading(hass, entity_id="switch.pool", watts=1200, age_seconds=5):
    """Attach a fresh or stale power reading to an entity."""
    hass.states.set(
        entity_id,
        str(watts),
        {"unit_of_measurement": "W"},
        last_updated=ha_stubs.utcnow() - timedelta(seconds=age_seconds),
    )


def make_finding():
    """Return one bilingual risk finding."""
    return RiskFinding(
        code="stale_data",
        severity=FindingSeverity.WARNING,
        module_id="core",
        title_de="Daten veraltet",
        title_en="Data is stale",
        detail_de="Die Netzleistung ist veraltet.",
        detail_en="Grid power is stale.",
        repair_de="Sensor prüfen.",
        repair_en="Check the sensor.",
        timestamp=ha_stubs.utcnow(),
    )


def audit_entries(runtime, kind):
    """Return audit entries of one kind, newest first."""
    return [entry for entry in runtime.audit.entries() if entry.kind.value == kind]


class HomeAssistantStandInTest(unittest.TestCase):
    """The stand-ins must not silently hide a missing interface."""

    def setUp(self):
        # The notification recorder is shared, because the real Home Assistant
        # notification service is global too. Tests must not depend on the order
        # in which modules happen to run.
        ha_stubs.persistent_notification.created.clear()
        self.addCleanup(ha_stubs.persistent_notification.created.clear)

    def test_unknown_attribute_is_reported_instead_of_returning_none(self):
        module = ha_stubs.StubModule("homeassistant.something")
        with self.assertRaises(AttributeError) as raised:
            _ = module.not_reproduced
        self.assertIn("not reproduced", str(raised.exception))

    def test_missing_notification_support_is_tolerated(self):
        runtime, _hass = make_runtime()
        components = ha_stubs.sys.modules["homeassistant.components"]
        saved_module = ha_stubs.sys.modules.pop("homeassistant.components.persistent_notification")
        saved_attribute = components.__dict__.pop("persistent_notification", None)
        try:
            runtime._notify(make_finding())  # must not raise
        finally:
            if saved_attribute is not None:
                components.persistent_notification = saved_attribute
            ha_stubs.sys.modules["homeassistant.components.persistent_notification"] = saved_module
        self.assertEqual([], ha_stubs.persistent_notification.created)


class SnapshotContractTest(unittest.TestCase):
    """The panel reads these keys, so the runtime must keep providing them."""

    def test_snapshot_keeps_the_keys_the_panel_uses(self):
        runtime, _hass = make_runtime()
        required = {
            "ai",
            "audit",
            "calibration",
            "devices",
            "emergency_stop",
            "forecast",
            "language",
            "manual_overrides",
            "modules",
            "plans",
            "privacy",
            "security",
            "settings",
            "summary",
            "terminal",
            "theme",
            "tutorial_done",
            "version",
        }
        snapshot = runtime.snapshot()
        self.assertTrue(required.issubset(set(snapshot)), sorted(required - set(snapshot)))

    def test_device_snapshot_exposes_the_flags_the_buttons_depend_on(self):
        runtime, hass = make_runtime()
        register_device(runtime)
        give_reading(hass)

        device = next(iter(runtime.snapshot()["devices"]))

        # The panel shows a switch-off button for a controllable device and
        # only shows switch-on once automation was released.
        self.assertTrue(device["controllable"])
        self.assertFalse(device["automation_allowed"])
        self.assertIn("limits", device)
        self.assertIn("decision", device)
        self.assertIn("warnings", device)

    def test_unverified_device_reports_missing_limits(self):
        runtime, hass = make_runtime()
        register_device(runtime)
        give_reading(hass)
        device = next(iter(runtime.snapshot()["devices"]))
        self.assertIn("limits_not_verified", device["warnings"])

    def test_a_configured_meter_is_used_for_the_summary(self):
        runtime, hass = make_runtime(**{CONF_METER_ENTITY: "sensor.grid", CONF_METER_MODE: "signed_net"})
        hass.states.set("sensor.grid", "1500", {"unit_of_measurement": "W"})

        summary = runtime.snapshot()["summary"]

        self.assertEqual(1500, summary["grid_import_w"])
        self.assertEqual(0, summary["grid_export_w"])

    def test_an_empty_configuration_does_not_invent_devices(self):
        runtime, _hass = make_runtime()
        snapshot = runtime.snapshot()
        self.assertEqual([], snapshot["devices"])
        self.assertEqual([], snapshot["plans"])

    def test_charging_plans_carry_names_not_only_entity_ids(self):
        runtime, hass = make_runtime()
        register_device(
            runtime,
            "switch.wallbox",
            kind="ev_charger",
            name="Garage Wallbox",
            capabilities=["set_power", "measure_power"],
            limits={"verified": True, "max_power_w": 11000},
            automations_allowed=True,
        )
        register_device(
            runtime,
            "sensor.id4",
            kind="ev",
            name="Auto ID4",
            capabilities=["measure_soc"],
            limits={"verified": True, "battery_capacity_kwh": 77, "min_soc": 0, "max_soc": 100},
            target_soc=80,
        )
        hass.states.set("sensor.id4", "50", {"battery_level": 50})

        plans = runtime.snapshot()["plans"]

        self.assertTrue(plans, "a configured car and wallbox must produce a plan")
        self.assertEqual("Garage Wallbox", plans[0]["wallbox_name"])
        self.assertEqual("Auto ID4", plans[0]["vehicle_name"])
        # The ids stay available for linking, the names are for the user.
        self.assertEqual("switch.wallbox", plans[0]["wallbox_id"])

    def test_a_nickname_wins_over_the_technical_name(self):
        runtime, _hass = make_runtime()
        register_device(runtime, "switch.pool", nickname="Pumpe hinten")
        device = next(iter(runtime.snapshot()["devices"]))
        self.assertEqual("Pumpe hinten", device["name"])


class ModuleConfigurationTest(unittest.TestCase):
    """The core module is mandatory, optional modules stay consistent."""

    def test_only_the_core_module_runs_on_a_fresh_install(self):
        runtime, _hass = make_runtime()
        self.assertEqual({CORE_MODULE_ID}, runtime.enabled)

    def test_the_core_module_can_never_be_disabled(self):
        runtime, _hass = make_runtime()
        result = runtime.set_module(CORE_MODULE_ID, False)
        self.assertFalse(result["ok"])
        self.assertEqual("core_required", result["error"])
        self.assertIn(CORE_MODULE_ID, runtime.enabled)

    def test_an_unknown_module_is_rejected(self):
        runtime, _hass = make_runtime()
        result = runtime.set_module("does_not_exist", True)
        self.assertFalse(result["ok"])
        self.assertEqual("unknown_module", result["error"])

    def test_enabling_a_module_also_enables_its_dependencies(self):
        runtime, _hass = make_runtime()
        runtime.set_module("mobility_calendar", True)
        result = runtime.set_module("ev_wallbox_link", True)
        self.assertTrue(result["ok"])
        self.assertIn("mobility_calendar", runtime.enabled)
        self.assertIn("ev_wallbox_link", runtime.enabled)

    def test_a_module_in_use_cannot_be_disabled_silently(self):
        runtime, _hass = make_runtime()
        runtime.set_module("ev_wallbox_link", True)
        result = runtime.set_module("mobility_calendar", False)
        self.assertFalse(result["ok"])
        self.assertEqual("dependent_modules_enabled", result["error"])
        self.assertIn("ev_wallbox_link", result["dependents"])
        self.assertIn("mobility_calendar", runtime.enabled)

    def test_a_module_without_dependents_can_be_disabled_again(self):
        runtime, _hass = make_runtime()
        runtime.set_module("price_cost", True)
        self.assertTrue(runtime.set_module("price_cost", False)["ok"])
        self.assertNotIn("price_cost", runtime.enabled)


class DeviceRegistrationTest(unittest.TestCase):
    """Registration must never hand out automation by itself."""

    def test_registration_defaults_to_no_automation(self):
        runtime, _hass = make_runtime()
        result = register_device(runtime)
        self.assertTrue(result["ok"])
        self.assertFalse(result["device"]["automations_allowed"])
        self.assertEqual("no_automation", result["device"]["fallback"])

    def test_registration_without_a_device_id_is_rejected(self):
        runtime, _hass = make_runtime()
        result = runtime.register_device({"name": "without an id"})
        self.assertFalse(result["ok"])
        self.assertEqual("missing_device_id", result["error"])

    def test_unknown_kind_and_capabilities_fall_back_to_safe_values(self):
        runtime, _hass = make_runtime()
        result = runtime.register_device(
            {
                "device_id": "switch.odd",
                "kind": "made_up_kind",
                "capabilities": ["teleport", "switch"],
            }
        )
        self.assertEqual("unknown", result["device"]["kind"])
        self.assertEqual(["switch"], result["device"]["capabilities"])

    def test_manual_override_only_touches_the_named_device(self):
        runtime, _hass = make_runtime()
        register_device(runtime, "switch.a")
        register_device(runtime, "switch.b")

        runtime.set_manual_override("switch.a", True)
        self.assertEqual({"switch.a"}, runtime.manual_overrides)

        runtime.set_manual_override("switch.a", False)
        self.assertEqual(set(), runtime.manual_overrides)


class DeviceCommandSafetyTest(unittest.TestCase):
    """Every command passes the central gate - this is the safety contract."""

    def test_an_unknown_device_is_rejected(self):
        runtime, _hass = make_runtime()
        result = run(runtime.async_set_device_state(device_id="switch.ghost", turn_on=False))
        self.assertFalse(result["ok"])
        self.assertEqual("unknown_device", result["error"])

    def test_switching_on_requires_an_explicit_confirmation(self):
        runtime, hass = make_runtime()
        register_device(runtime, automations_allowed=True, limits={"verified": True, "max_power_w": 2000})
        give_reading(hass)

        result = run(runtime.async_set_device_state(device_id="switch.pool", turn_on=True))

        self.assertFalse(result["ok"])
        self.assertEqual("confirmation_required", result["error"])
        self.assertEqual([], hass.services.calls)

    def test_a_device_without_an_actuator_cannot_be_switched_at_all(self):
        runtime, hass = make_runtime()
        register_device(
            runtime,
            "sensor.pv",
            kind="pv",
            capabilities=["measure_power"],
            automations_allowed=True,
        )
        give_reading(hass, "sensor.pv", watts=5000)

        result = run(runtime.async_set_device_state(device_id="sensor.pv", turn_on=False))

        self.assertFalse(result["ok"])
        self.assertEqual("not_controllable", result["error"])
        self.assertEqual([], hass.services.calls)

    def test_switching_off_stays_a_safe_stop_during_an_emergency_stop(self):
        runtime, hass = make_runtime()
        register_device(runtime)
        give_reading(hass)
        runtime.set_emergency_stop(True)

        result = run(runtime.async_set_device_state(device_id="switch.pool", turn_on=False))

        self.assertTrue(result["ok"], result)
        self.assertEqual(1, len(hass.services.called("switch", "turn_off")))
        actions = audit_entries(runtime, KIND_ACTION)
        self.assertEqual("safe_stop", actions[0].reason)

    def test_an_emergency_stop_blocks_switching_on(self):
        runtime, hass = make_runtime()
        register_device(runtime, automations_allowed=True, limits={"verified": True, "max_power_w": 2000})
        give_reading(hass)
        runtime.set_emergency_stop(True)

        result = run(
            runtime.async_set_device_state(device_id="switch.pool", turn_on=True, user_confirmed=True)
        )

        self.assertFalse(result["ok"])
        self.assertEqual("emergency_stop", result["error"])
        self.assertEqual([], hass.services.called("switch", "turn_on"))

    def test_stale_readings_block_switching_on_but_not_switching_off(self):
        runtime, hass = make_runtime()
        register_device(runtime, automations_allowed=True, limits={"verified": True, "max_power_w": 2000})
        give_reading(hass, age_seconds=DEFAULT_STALE_AFTER_SECONDS + 60)

        on = run(runtime.async_set_device_state(device_id="switch.pool", turn_on=True, user_confirmed=True))
        self.assertFalse(on["ok"], on)
        self.assertNotEqual("ok", on["error"])
        self.assertEqual([], hass.services.called("switch", "turn_on"))

        off = run(runtime.async_set_device_state(device_id="switch.pool", turn_on=False))
        self.assertTrue(off["ok"], off)

    def test_a_released_device_can_be_switched_on_and_is_audited(self):
        runtime, hass = make_runtime()
        register_device(runtime, automations_allowed=True, limits={"verified": True, "max_power_w": 2000})
        give_reading(hass)

        result = run(
            runtime.async_set_device_state(device_id="switch.pool", turn_on=True, user_confirmed=True)
        )

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["turn_on"])
        calls = hass.services.called("switch", "turn_on")
        self.assertEqual(1, len(calls))
        self.assertEqual("switch.pool", calls[0]["data"]["entity_id"])
        self.assertEqual(1, len(audit_entries(runtime, KIND_ACTION)))

    def test_manual_override_releases_a_device_that_has_no_automation(self):
        runtime, hass = make_runtime()
        register_device(runtime, limits={"verified": True, "max_power_w": 2000})
        give_reading(hass)
        runtime.set_manual_override("switch.pool", True)

        result = run(
            runtime.async_set_device_state(device_id="switch.pool", turn_on=True, user_confirmed=True)
        )

        self.assertTrue(result["ok"], result)

    def test_a_blocked_command_is_written_to_the_audit_log(self):
        runtime, hass = make_runtime()
        register_device(runtime, automations_allowed=True, limits={"verified": True, "max_power_w": 2000})
        give_reading(hass, age_seconds=DEFAULT_STALE_AFTER_SECONDS + 60)

        run(runtime.async_set_device_state(device_id="switch.pool", turn_on=True, user_confirmed=True))

        decisions = audit_entries(runtime, KIND_DECISION)
        self.assertEqual(1, len(decisions))
        self.assertNotEqual("ok", decisions[0].reason)


class PersistenceTest(unittest.TestCase):
    """Settings are stored, secrets and measurements are not, removal is complete."""

    def test_settings_round_trip_through_storage(self):
        runtime, hass = make_runtime()
        runtime.set_module("price_cost", True)
        runtime.update_settings({"settings": {"language": "en", "grid_import_limit_w": 9000}})
        run(runtime.async_save())

        reloaded, _same_hass = make_runtime(hass)
        run(reloaded.async_load())

        self.assertEqual("en", reloaded.settings["language"])
        self.assertEqual(9000, reloaded.settings["grid_import_limit_w"])
        self.assertIn("price_cost", reloaded.enabled)

    def test_only_configuration_is_written_to_storage(self):
        runtime, hass = make_runtime()
        run(runtime.async_save())
        stored = hass.data[STORED_KEY]
        self.assertEqual({"modules", "settings", "terminal", "privacy", "ai", "devices"}, set(stored))

    def test_the_api_key_is_never_written_to_storage(self):
        runtime, hass = make_runtime()
        runtime.update_settings({"ai": {"api_key": "super-secret-token", "provider_id": "groq"}})

        run(runtime.async_save())
        stored = hass.data[STORED_KEY]

        self.assertNotIn("api_key", stored["ai"])
        self.assertNotIn("super-secret-token", str(stored))

    def test_a_supplied_api_key_is_reduced_to_a_flag(self):
        runtime, _hass = make_runtime()
        runtime.update_settings({"ai": {"api_key": "super-secret-token"}})
        self.assertNotIn("api_key", runtime.ai)
        self.assertTrue(runtime.ai["api_key_set"])

    def test_measured_values_and_entity_ids_are_not_persisted(self):
        runtime, hass = make_runtime(**{CONF_PV_ENTITY: "sensor.pv"})
        hass.states.set("sensor.pv", "4000", {"unit_of_measurement": "W"})
        runtime.snapshot()

        run(runtime.async_save())
        stored_text = str(hass.data[STORED_KEY])

        self.assertNotIn("sensor.pv", stored_text)
        self.assertNotIn("4000", stored_text)

    def test_removing_the_integration_deletes_its_own_store(self):
        runtime, hass = make_runtime()
        run(runtime.async_save())
        self.assertIn(STORED_KEY, hass.data)

        run(runtime.async_remove_store())
        self.assertNotIn(STORED_KEY, hass.data)

    def test_a_first_run_without_stored_data_uses_safe_defaults(self):
        runtime, _hass = make_runtime()
        run(runtime.async_load())
        self.assertEqual({CORE_MODULE_ID}, runtime.enabled)
        self.assertEqual("de", runtime.settings["language"])
        self.assertFalse(runtime.settings["emergency_stop"])
        self.assertFalse(runtime.settings["tutorial_done"])
        self.assertFalse(runtime.settings["grid_charging_allowed"])


class NotificationLanguageTest(unittest.TestCase):
    """Notifications are user-facing, so they follow the chosen language."""

    def setUp(self):
        ha_stubs.persistent_notification.created.clear()
        self.addCleanup(ha_stubs.persistent_notification.created.clear)

    def test_notification_is_german_by_default(self):
        runtime, _hass = make_runtime()
        runtime._notify(make_finding())

        self.assertEqual(1, len(ha_stubs.persistent_notification.created))
        sent = ha_stubs.persistent_notification.created[0]
        self.assertIn("Was du tun kannst", sent["message"])
        self.assertIn("Sensor prüfen.", sent["message"])
        self.assertIn("Daten veraltet", sent["title"])

    def test_notification_follows_the_english_language_setting(self):
        runtime, _hass = make_runtime()
        runtime.settings["language"] = "en"
        runtime._notify(make_finding())

        sent = ha_stubs.persistent_notification.created[0]
        self.assertIn("What you can do", sent["message"])
        self.assertIn("Check the sensor.", sent["message"])
        self.assertIn("Data is stale", sent["title"])
        combined = sent["message"] + sent["title"]
        for german in ("Was du tun kannst", "Sensor prüfen.", "Daten veraltet"):
            self.assertNotIn(german, combined)

    def test_notification_never_contains_the_api_key(self):
        runtime, _hass = make_runtime()
        runtime.ai["api_key"] = "super-secret-token"
        runtime._notify(make_finding())
        self.assertNotIn("super-secret-token", str(ha_stubs.persistent_notification.created))


if __name__ == "__main__":
    unittest.main()
