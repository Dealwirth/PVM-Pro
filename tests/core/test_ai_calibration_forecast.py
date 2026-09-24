"""Contract tests for AI advice, calibration and forecasting."""

from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime, timedelta

from custom_components.pv_manager.core.ai import (
    PROVIDER_CATALOG,
    AIAdvisor,
    AIRequest,
    GroqProvider,
    LocalRulesProvider,
    ReportInterval,
    ReportSchedule,
)
from custom_components.pv_manager.core.calibration import (
    CalibrationLimits,
    CalibrationRun,
    CalibrationState,
)
from custom_components.pv_manager.core.forecast import (
    BaselineProfile,
    SolarForecastInput,
    build_baseline,
    confidence_label,
    consumption_forecast,
    solar_forecast,
    solar_surplus,
    total_kwh,
    weather_efficiency,
)
from custom_components.pv_manager.core.privacy import AliasVault, PrivacyMode, PrivacySettings
from custom_components.pv_manager.core.security import (
    SecurityTerminal,
)

UTC = UTC
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


class FakeAIProvider:
    provider_id = "fake"
    local = False

    def __init__(self) -> None:
        self.requests: list[AIRequest] = []

    async def complete(self, request: AIRequest) -> str:
        self.requests.append(request)
        return "Warnung: Sensor prüfen und Verbindung kontrollieren."


class ProviderCatalogTests(unittest.TestCase):
    def test_groq_is_suggested(self) -> None:
        groq = next(info for info in PROVIDER_CATALOG if info.provider_id == "groq")
        self.assertTrue(groq.suggested)
        self.assertFalse(groq.local)

    def test_local_rules_are_suggested(self) -> None:
        local = next(info for info in PROVIDER_CATALOG if info.provider_id == "local_rules")
        self.assertTrue(local.local)
        self.assertIn("keine Daten", local.privacy_note_de)

    def test_provider_request_has_no_local_ids(self) -> None:
        provider = GroqProvider(model="test-model", transport=lambda request: None)  # type: ignore[arg-type]
        request = AIRequest(
            preview=type("Preview", (), {"payload": {"alias": "device-abc"}})(),
            prompt_de="prompt",
            prompt_en="prompt",
        )
        built = provider.build_request(request)
        self.assertEqual(built["model"], "test-model")
        self.assertNotIn("sensor.", str(built))
        self.assertIn("keine Geräte steuern", built["messages"][0]["content"])


class AdvisorTests(unittest.TestCase):
    def advisor(self, mode: PrivacyMode) -> AIAdvisor:
        return AIAdvisor(
            providers={"fake": FakeAIProvider(), "local_rules": LocalRulesProvider()},
            settings=PrivacySettings(mode=mode),
        )

    def test_local_advisor_works_without_network(self) -> None:
        advisor = AIAdvisor(providers={"local_rules": LocalRulesProvider()})
        preview = advisor.prepare(
            vault=AliasVault(secret=b"x"),
            provider_id="local_rules",
            modules=[],
            report=SecurityTerminal().evaluate(modules={}, now=NOW),
        )
        report = asyncio.run(advisor.analyse(preview, now=NOW, provider_id="local_rules"))
        self.assertEqual(report.provider_id, "local_rules")
        self.assertFalse(report.external_data_sent)
        self.assertFalse(report.ai_can_control)

    def test_external_requires_non_local_mode(self) -> None:
        advisor = self.advisor(PrivacyMode.LOCAL_ONLY)
        preview = advisor.prepare(
            vault=AliasVault(secret=b"x"),
            provider_id="fake",
            modules=[],
            report=SecurityTerminal().evaluate(modules={}, now=NOW),
        )
        report = asyncio.run(advisor.analyse(preview, now=NOW, provider_id="fake", user_confirmed=True))
        self.assertIn("local_mode", report.summary_de)

    def test_external_requires_confirmation(self) -> None:
        settings = PrivacySettings(mode=PrivacyMode.PSEUDONYMOUS, allow_external_provider=True)
        advisor = AIAdvisor(providers={"fake": FakeAIProvider()}, settings=settings)
        preview = advisor.prepare(
            vault=AliasVault(secret=b"x"),
            provider_id="fake",
            modules=[],
            report=SecurityTerminal().evaluate(modules={}, now=NOW),
        )
        report = asyncio.run(advisor.analyse(preview, now=NOW, provider_id="fake", user_confirmed=False))
        self.assertIn("preview_not_confirmed", report.summary_de)

    def test_external_runs_when_confirmed(self) -> None:
        settings = PrivacySettings(mode=PrivacyMode.PSEUDONYMOUS, allow_external_provider=True)
        advisor = AIAdvisor(providers={"fake": FakeAIProvider()}, settings=settings)
        preview = advisor.prepare(
            vault=AliasVault(secret=b"x"),
            provider_id="fake",
            modules=[{"id": "sensor.car", "kind": "ev"}],
            report=SecurityTerminal().evaluate(modules={}, now=NOW),
        )
        report = asyncio.run(advisor.analyse(preview, now=NOW, provider_id="fake", user_confirmed=True))
        self.assertTrue(report.external_data_sent)
        self.assertFalse(report.ai_can_control)
        self.assertTrue(report.repair_de)


class ScheduleTests(unittest.TestCase):
    def test_hourly_schedule(self) -> None:
        schedule = ReportSchedule(interval=ReportInterval.HOURLY, last_run=NOW)
        self.assertFalse(schedule.is_due(NOW + timedelta(minutes=30)))
        self.assertTrue(schedule.is_due(NOW + timedelta(hours=1)))

    def test_manual_schedule_never_auto_runs(self) -> None:
        schedule = ReportSchedule(interval=ReportInterval.MANUAL, last_run=NOW)
        self.assertFalse(schedule.is_due(NOW + timedelta(days=30)))

    def test_critical_forces_report(self) -> None:
        schedule = ReportSchedule(interval=ReportInterval.DAILY, last_run=NOW, force_on_critical=True)
        self.assertTrue(schedule.is_due(NOW + timedelta(minutes=1), critical=True))

    def test_on_error_only(self) -> None:
        schedule = ReportSchedule(interval=ReportInterval.ON_ERROR, last_run=NOW)
        self.assertFalse(schedule.is_due(NOW + timedelta(days=1)))
        self.assertTrue(schedule.is_due(NOW + timedelta(days=1), critical=True))


class CalibrationTests(unittest.TestCase):
    def make_run(self) -> CalibrationRun:
        return CalibrationRun(
            device_id="switch.pool",
            entity_id="switch.pool",
            limits=CalibrationLimits(
                max_power_w=1000,
                max_energy_kwh=0.2,
                max_seconds_on=60,
                baseline_seconds=1,
                off_seconds=1,
                repetitions=2,
            ),
        )

    def test_cannot_start_twice(self) -> None:
        run = self.make_run()
        run.start(NOW)
        ok, reason = run.can_start()
        self.assertFalse(ok)
        self.assertEqual(reason, "already_running")

    def test_aborts_when_grid_headroom_too_low(self) -> None:
        run = self.make_run()
        run.start(NOW)
        run.baseline_done(100.0, NOW + timedelta(seconds=2))
        allowed, reason = run.device_on_allowed(grid_headroom_w=100.0, device_power_w=500.0)
        self.assertFalse(allowed)
        self.assertEqual(reason, "grid_headroom_too_low")

    def test_aborts_when_device_power_exceeds_limit(self) -> None:
        run = self.make_run()
        run.start(NOW)
        run.baseline_done(100.0, NOW + timedelta(seconds=2))
        allowed, reason = run.device_on_allowed(grid_headroom_w=5000.0, device_power_w=2000.0)
        self.assertFalse(allowed)
        self.assertEqual(reason, "device_power_limit")

    def test_energy_budget_counts(self) -> None:
        run = self.make_run()
        run.start(NOW)
        run.baseline_done(100.0, NOW + timedelta(seconds=2))
        run.record_measurement(1000.0, seconds=60)
        self.assertAlmostEqual(run.used_energy_kwh, 1000 * 60 / 3_600_000)

    def test_finish_and_summary(self) -> None:
        run = self.make_run()
        run.start(NOW)
        run.baseline_done(100.0, NOW + timedelta(seconds=2))
        run.record_measurement(600.0, seconds=60)
        run.finish()
        self.assertEqual(run.state, CalibrationState.FINISHED)
        self.assertIn("500", run.summary_de())

    def test_abort_summary_warns_and_mentions_switch_off(self) -> None:
        run = self.make_run()
        run.abort("grid_headroom_too_low")
        self.assertIn("ausgeschaltet", run.summary_de())


class ForecastTests(unittest.TestCase):
    def test_cold_start_profile_is_used(self) -> None:
        profile = build_baseline([])
        value, confidence, samples = profile.expected(NOW)
        self.assertGreater(value, 0)
        self.assertLess(confidence, 0.3)
        self.assertEqual(samples, 0)

    def test_profile_learns_weekday_hour(self) -> None:
        profile = BaselineProfile()
        for _ in range(10):
            profile.add(NOW, 1.5)
        value, confidence, samples = profile.expected(NOW)
        self.assertAlmostEqual(value, 1.5)
        self.assertEqual(samples, 10)
        self.assertGreater(confidence, 0.5)

    def test_consumption_forecast_length(self) -> None:
        points = consumption_forecast(build_baseline([]), start=NOW, end=NOW + timedelta(hours=24))
        self.assertEqual(len(points), 24)
        self.assertGreater(total_kwh(points), 0)

    def test_weather_efficiency(self) -> None:
        clear, reason = weather_efficiency()
        cloudy, _ = weather_efficiency(cloud_coverage_pct=100)
        self.assertEqual(clear, 1.0)
        self.assertAlmostEqual(cloudy, 0.35)
        self.assertEqual(reason, "clear")

    def test_solar_forecast_applies_efficiency(self) -> None:
        points = solar_forecast(
            [SolarForecastInput(start=NOW, end=NOW + timedelta(hours=1), expected_kwh=4.0)],
            efficiency=0.5,
        )
        self.assertAlmostEqual(points[0].expected_kwh, 2.0)
        self.assertLess(points[0].lower_kwh, points[0].expected_kwh)

    def test_surplus(self) -> None:
        self.assertAlmostEqual(solar_surplus(solar_kwh=10, consumption_kwh=4, battery_room_kwh=1), 5.0)
        self.assertEqual(solar_surplus(solar_kwh=1, consumption_kwh=4), 0.0)

    def test_confidence_labels(self) -> None:
        self.assertEqual(confidence_label(0.9), "high")
        self.assertEqual(confidence_label(0.6), "medium")
        self.assertEqual(confidence_label(0.3), "low")
        self.assertEqual(confidence_label(0.1), "very_low")


if __name__ == "__main__":
    unittest.main()
