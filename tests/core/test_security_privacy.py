"""Contract tests for the security terminal and privacy engine."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from custom_components.pv_manager.core.privacy import (
    AliasVault,
    PrivacyMode,
    PrivacySettings,
    build_payload,
    contains_forbidden_key,
    sanitize_value,
)
from custom_components.pv_manager.core.security import (
    FindingSeverity,
    HealthStatus,
    ModuleContract,
    ModuleHealth,
    ReactionSpeed,
    SecurityLevel,
    SecurityTerminal,
    TerminalConfig,
)

UTC = UTC
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def healthy(contract: ModuleContract | None = None) -> ModuleHealth:
    contract = contract or ModuleContract(inputs={"core"}, outputs={"energy_balance"})
    return ModuleHealth(
        module_id="core",
        status=HealthStatus.READY,
        last_heartbeat=NOW,
        contract=contract,
        observed_inputs=set(contract.inputs),
        observed_outputs=set(contract.outputs),
    )


class SecurityTests(unittest.TestCase):
    def test_healthy_system(self) -> None:
        terminal = SecurityTerminal()
        report = terminal.evaluate(modules={"core": healthy()}, now=NOW)
        self.assertEqual(report.overall, FindingSeverity.INFO)
        self.assertEqual(report.score, 100)

    def test_stale_data_is_reported(self) -> None:
        terminal = SecurityTerminal()
        report = terminal.evaluate(
            modules={"core": healthy()},
            now=NOW,
            reading_ages={"Netz-Leistung": 400},
        )
        self.assertEqual(report.overall, FindingSeverity.WARNING)
        self.assertTrue(any(finding.code == "stale_reading" for finding in report.findings))

    def test_module_error_is_critical(self) -> None:
        health = healthy()
        health.status = HealthStatus.ERROR
        health.consecutive_failures = 3
        health.last_error_de = "Sensor fehlt"
        report = SecurityTerminal().evaluate(modules={"forecast_learning": health}, now=NOW)
        self.assertEqual(report.overall, FindingSeverity.CRITICAL)
        self.assertLess(report.score, 80)

    def test_contract_mismatch_is_warning(self) -> None:
        contract = ModuleContract(inputs={"core", "price_windows"}, outputs={"battery_strategy"})
        health = ModuleHealth(
            module_id="storage_grid",
            status=HealthStatus.READY,
            last_heartbeat=NOW,
            contract=contract,
            observed_inputs={"core"},
            observed_outputs={"battery_strategy"},
        )
        report = SecurityTerminal().evaluate(modules={"storage_grid": health}, now=NOW)
        self.assertTrue(any(finding.code == "module_io_contract" for finding in report.findings))

    def test_emergency_stop_is_critical(self) -> None:
        report = SecurityTerminal().evaluate(modules={"core": healthy()}, now=NOW, emergency_stop=True)
        self.assertEqual(report.overall, FindingSeverity.CRITICAL)

    def test_intervention_respects_allowlist(self) -> None:
        config = TerminalConfig(
            level=SecurityLevel.INTERVENE,
            allow_module_pause=True,
        )
        terminal = SecurityTerminal(config)
        health = healthy()
        health.status = HealthStatus.ERROR
        health.consecutive_failures = 5
        report = terminal.evaluate(modules={"forecast_learning": health}, now=NOW)
        self.assertIn("forecast_learning", report.paused_modules)

    def test_observe_never_pauses(self) -> None:
        terminal = SecurityTerminal(TerminalConfig(level=SecurityLevel.OBSERVE, allow_module_pause=True))
        health = healthy()
        health.status = HealthStatus.ERROR
        health.consecutive_failures = 5
        report = terminal.evaluate(modules={"forecast_learning": health}, now=NOW)
        self.assertEqual(report.paused_modules, [])

    def test_core_is_never_paused(self) -> None:
        config = TerminalConfig(level=SecurityLevel.INTERVENE, allow_module_pause=True)
        health = healthy()
        health.status = HealthStatus.ERROR
        health.consecutive_failures = 5
        report = SecurityTerminal(config).evaluate(modules={"core": health}, now=NOW)
        self.assertNotIn("core", report.paused_modules)

    def test_external_ai_is_visible(self) -> None:
        report = SecurityTerminal().evaluate(
            modules={"core": healthy()},
            now=NOW,
            ai_enabled=True,
            privacy_mode="pseudonymous",
        )
        self.assertTrue(any(finding.code == "external_ai_active" for finding in report.findings))

    def test_repeated_notifications_are_deduplicated(self) -> None:
        terminal = SecurityTerminal()
        health = healthy()
        health.status = HealthStatus.ERROR
        health.consecutive_failures = 3
        report = terminal.evaluate(modules={"forecast_learning": health}, now=NOW)
        first = terminal.due_notifications(report.findings, now=NOW)
        second = terminal.due_notifications(report.findings, now=NOW + timedelta(minutes=1))
        repeat = terminal.due_notifications(report.findings, now=NOW + timedelta(minutes=20))
        self.assertTrue(first)
        self.assertEqual(second, [])
        self.assertTrue(repeat)

    def test_reaction_speeds_available(self) -> None:
        self.assertIn(ReactionSpeed.IMMEDIATE.value, [speed.value for speed in ReactionSpeed])
        self.assertIn(ReactionSpeed.FIVE_MINUTES.value, [speed.value for speed in ReactionSpeed])


class PrivacyTests(unittest.TestCase):
    def test_alias_rotates_per_report(self) -> None:
        vault = AliasVault(secret=b"unit-test-secret")
        first = vault.alias_for("sensor.real_device", report_id="report-1")
        second = vault.alias_for("sensor.real_device", report_id="report-2")
        self.assertNotEqual(first, second)
        self.assertEqual(vault.resolve_local(first), "sensor.real_device")

    def test_local_payload_contains_no_devices(self) -> None:
        vault = AliasVault(secret=b"unit-test-secret")
        preview = build_payload(
            vault=vault,
            provider="local_rules",
            settings=PrivacySettings(mode=PrivacyMode.LOCAL_ONLY),
            devices=[{"id": "sensor.car", "kind": "ev", "capabilities": ["measure_soc"]}],
            findings=[],
            summary={},
        )
        self.assertNotIn("devices", preview.payload)
        self.assertIn("devices", preview.omitted)
        self.assertIn("Lokalmodus", preview.warning_de)

    def test_pseudonymous_payload_has_alias_not_real_id(self) -> None:
        vault = AliasVault(secret=b"unit-test-secret")
        preview = build_payload(
            vault=vault,
            provider="groq",
            settings=PrivacySettings(mode=PrivacyMode.PSEUDONYMOUS),
            devices=[
                {
                    "id": "sensor.tesla_vin_123",
                    "kind": "ev",
                    "capabilities": ["measure_soc"],
                    "metrics": {"soc": 42},
                }
            ],
            findings=[],
            summary={},
        )
        text = str(preview.payload)
        self.assertNotIn("tesla_vin", text)
        self.assertIn("device-", text)
        self.assertEqual(contains_forbidden_key(preview.payload), [])
        self.assertIn("Pseudonymisierte", preview.warning_de)

    def test_forbidden_keys_are_detected(self) -> None:
        self.assertEqual(contains_forbidden_key({"entity_id": "sensor.x"}), ["entity_id"])
        self.assertEqual(contains_forbidden_key({"nested": [{"location": "x"}]}), ["location"])

    def test_sanitize_redacts_identifying_text(self) -> None:
        self.assertEqual(sanitize_value("mail me at test@example.com"), "[redacted]")
        self.assertEqual(sanitize_value("https://example.com"), "[redacted]")
        self.assertEqual(sanitize_value("power"), "power")
        self.assertLessEqual(len(sanitize_value("x" * 500)), 80)

    def test_sanitize_drops_forbidden_nested_keys(self) -> None:
        cleaned = sanitize_value({"device_name": "Tesla", "power_w": 4200, "nested": {"vin": "X"}})
        self.assertEqual(cleaned, {"power_w": 4200, "nested": {}})

    def test_preview_warning_for_extended_mode(self) -> None:
        vault = AliasVault(secret=b"unit-test-secret")
        preview = build_payload(
            vault=vault,
            provider="openai_compatible",
            settings=PrivacySettings(mode=PrivacyMode.EXTENDED, include_energy_history=True),
            devices=[],
            findings=[],
            summary={"energy_history": [1, 2, 3]},
        )
        self.assertIn("Erweiterte", preview.warning_de)


if __name__ == "__main__":
    unittest.main()
