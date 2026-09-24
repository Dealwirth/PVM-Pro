"""Tests for the AI transport in ``ai_client.py``.

This is the only code path that sends data off the machine, so it deserves the
strictest checks in the project. The provider takes an injected transport, and
``ai_client.build_provider_factory`` builds one around Home Assistant's aiohttp
session - which :mod:`tests.ha.ha_stubs` replaces with a recorder. That means the
*real* request can be inspected instead of a hand-written approximation.

``ha_stubs.install()`` must run before the integration is imported.
"""

from __future__ import annotations

import asyncio
import unittest

from tests.ha import ha_stubs

ha_stubs.install()

from custom_components.pv_manager.ai_client import (  # noqa: E402
    build_provider_factory,
    provider_info,
)
from custom_components.pv_manager.const import CONF_AI_API_KEY  # noqa: E402
from custom_components.pv_manager.core.ai import OpenAICompatibleProvider  # noqa: E402
from custom_components.pv_manager.runtime import PVManagerRuntime  # noqa: E402

ENTRY_ID = "test-entry"
API_KEY = "super-secret-token"

# Values that must never reach an external provider. They are chosen to be
# unmistakable so a match cannot be a coincidence.
FORBIDDEN = (
    "Poolpumpe",  # device name
    "Pumpe hinten",  # nickname
    "switch.pool",  # entity id
    "calendar.urlaub",  # calendar entity
    "weather.home",  # weather entity
    "sensor.wallbox",  # wallbox entity
    "Waschen und packen",  # calendar summary text
    "52.52",  # latitude
    "13.405",  # longitude
)


def run(coroutine):
    """Run one coroutine to completion."""
    return asyncio.run(coroutine)


def make_runtime(sensitive_setup=True):
    """Return a runtime with devices, calendar and weather configured."""
    options = {}
    if sensitive_setup:
        options = {
            "meter_entity": "sensor.grid",
            "pv_entity": "sensor.pv",
            "calendar_entity": "calendar.urlaub",
            "weather_entity": "weather.home",
            CONF_AI_API_KEY: API_KEY,
        }
    hass = ha_stubs.FakeHass()
    entry = ha_stubs.FakeConfigEntry(options=options, entry_id=ENTRY_ID)
    runtime = PVManagerRuntime(hass, entry)
    if sensitive_setup:
        # Pseudonymous mode is the only mode in which device context may leave
        # the system at all; local_only must omit it entirely.
        runtime.privacy["mode"] = "pseudonymous"
        runtime._apply_privacy_settings()
        runtime.register_device(
            {
                "device_id": "switch.pool",
                "entity_id": "switch.pool",
                "name": "Poolpumpe",
                "nickname": "Pumpe hinten",
                "kind": "flexible_load",
                "capabilities": ["switch", "measure_power"],
                "limits": {"verified": True, "max_power_w": 2000},
            }
        )
        runtime.register_device(
            {
                "device_id": "sensor.wallbox",
                "entity_id": "sensor.wallbox",
                "name": "Garage Wallbox",
                "kind": "ev_charger",
                "capabilities": ["set_power", "measure_power"],
                "limits": {"verified": True, "max_power_w": 11000},
            }
        )
        hass.states.set("sensor.grid", "1200", {"unit_of_measurement": "W"})
        hass.states.set("sensor.pv", "4200", {"unit_of_measurement": "W"})
        hass.states.set("switch.pool", "800", {"unit_of_measurement": "W"})
        hass.states.set("sensor.wallbox", "0", {"unit_of_measurement": "W"})
        hass.states.set(
            "calendar.urlaub",
            "on",
            {
                "message": "Waschen und packen",
                "start_time": "2026-09-24T07:30:00+00:00",
                "end_time": "2026-09-24T08:00:00+00:00",
            },
        )
        hass.states.set(
            "weather.home",
            "sunny",
            {
                "temperature": 18.5,
                "cloud_coverage": 10,
                "latitude": 52.5200,
                "longitude": 13.4050,
            },
        )
    # prepare_ai_preview reads last_snapshot, which only a refresh fills.
    run(runtime.async_refresh())
    return runtime, hass


def build_transport(runtime, hass, provider_id="groq"):
    """Return a real provider built exactly like the integration builds it."""
    factory = build_provider_factory(hass, runtime)
    return factory(provider_id)


class AiTransportPrivacyTest(unittest.TestCase):
    """Nothing identifying may leave the machine."""

    def test_an_external_request_contains_no_identifying_values(self):
        runtime, hass = make_runtime()
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass)

        run(provider.complete(runtime._ai_preview))

        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, str(hass.http_session.requests), f"{forbidden!r} was sent")
        # Parameters that only reveal the home's shape are fine, entities are not.
        self.assertNotIn("entity", str(hass.http_session.requests[0]["json"]).lower())

    def test_the_local_only_mode_sends_no_device_context_at_all(self):
        runtime, hass = make_runtime()
        runtime.privacy["mode"] = "local_only"
        runtime._apply_privacy_settings()
        runtime.prepare_ai_preview()

        payload = runtime._ai_preview.preview.payload

        self.assertNotIn("devices", payload)
        self.assertIn("devices", runtime._ai_preview.preview.omitted)

    def test_the_payload_carries_aliases_instead_of_device_identity(self):
        runtime, hass = make_runtime()
        runtime.prepare_ai_preview()
        payload = runtime._ai_preview.preview.payload

        self.assertTrue(payload.get("devices"), "the preview should describe devices")
        for device in payload["devices"]:
            self.assertTrue(
                str(device.get("alias", "")).startswith("device-"),
                f"device id is not an alias: {device.get('alias')!r}",
            )
            # The raw entity id is only ever used as the vault lookup key.
            self.assertNotIn("id", device)
        self.assertNotIn("Poolpumpe", str(payload))
        self.assertNotIn("switch.pool", str(payload))

    def test_the_api_key_travels_only_as_an_authorization_header(self):
        runtime, hass = make_runtime()
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass)

        run(provider.complete(runtime._ai_preview))

        request = hass.http_session.requests[0]
        self.assertEqual(f"Bearer {API_KEY}", request["headers"]["Authorization"])
        self.assertNotIn(API_KEY, str(request["json"]))

    def test_a_local_provider_never_receives_the_api_key(self):
        runtime, hass = make_runtime()
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass, provider_id="local_model")

        run(provider.complete(runtime._ai_preview))

        headers = hass.http_session.requests[0]["headers"]
        self.assertNotIn("Authorization", headers)

    def test_the_local_rules_provider_does_not_touch_the_network(self):
        runtime, hass = make_runtime()
        runtime.prepare_ai_preview()

        answer = run(runtime.advisor.providers["local_rules"].complete(runtime._ai_preview))

        self.assertTrue(answer)
        self.assertEqual([], hass.http_session.requests)

    def test_a_rejected_request_does_not_echo_the_whole_response(self):
        runtime, hass = make_runtime()
        hass.http_session.response = ha_stubs.FakeHTTPResponse(status=500, text="x" * 5000)
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass)

        with self.assertRaises(RuntimeError) as raised:
            run(provider.complete(runtime._ai_preview))

        message = str(raised.exception)
        self.assertIn("provider_http_500", message)
        self.assertLess(len(message), 300, "the response body should be truncated")


class AiTransportLanguageTest(unittest.TestCase):
    """The advisory must be written in the language the user selected."""

    def test_a_german_user_sends_the_german_prompt(self):
        runtime, hass = make_runtime()
        runtime.settings["language"] = "de"
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass)

        run(provider.complete(runtime._ai_preview))

        messages = hass.http_session.requests[0]["json"]["messages"]
        self.assertIn("Du bist ein sicherheitsorientierter", messages[0]["content"])
        self.assertTrue(any("Analysiere diesen" in m["content"] for m in messages))

    def test_an_english_user_sends_the_english_prompt(self):
        runtime, hass = make_runtime()
        runtime.settings["language"] = "en"
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass)

        run(provider.complete(runtime._ai_preview))

        sent = hass.http_session.sent_text()
        self.assertIn("You are a safety-oriented", sent)
        self.assertIn("Analyse this pseudonymized", sent)
        for german in ("Du bist ein sicherheitsorientierter", "Analysiere diesen", "Daten:"):
            self.assertNotIn(german, sent)

    def test_the_english_system_prompt_still_forbids_control(self):
        runtime, hass = make_runtime()
        runtime.settings["language"] = "en"
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass)

        run(provider.complete(runtime._ai_preview))

        system = hass.http_session.requests[0]["json"]["messages"][0]["content"]
        self.assertIn("must not control devices", system)

    def test_the_payload_itself_declares_the_users_language(self):
        runtime, hass = make_runtime()
        runtime.settings["language"] = "en"
        runtime.prepare_ai_preview()
        self.assertEqual("en", runtime._ai_preview.preview.payload["locale"])

        runtime.settings["language"] = "de"
        runtime.prepare_ai_preview()
        self.assertEqual("de", runtime._ai_preview.preview.payload["locale"])

    def test_the_local_rules_answer_follows_the_language(self):
        runtime, hass = make_runtime()
        runtime.settings["language"] = "en"
        runtime.prepare_ai_preview()

        english = run(runtime.advisor.providers["local_rules"].complete(runtime._ai_preview))

        runtime.settings["language"] = "de"
        runtime.prepare_ai_preview()
        german = run(runtime.advisor.providers["local_rules"].complete(runtime._ai_preview))

        self.assertNotEqual(english, german)
        self.assertNotIn("Keine Auffälligkeiten", english)


class AiProviderCatalogueTest(unittest.TestCase):
    """The UI must be able to explain every provider, in both languages."""

    def test_every_catalogue_entry_has_both_names_and_both_notes(self):
        for provider_id in ("local_rules", "local_model", "groq", "openai_compatible"):
            info = provider_info(provider_id)
            self.assertTrue(info, provider_id)
            for field in ("name_de", "name_en", "privacy_note_de", "privacy_note_en"):
                self.assertTrue(info.get(field), f"{provider_id}.{field} is empty")

    def test_groq_is_marked_external_and_suggested(self):
        info = provider_info("groq")
        self.assertFalse(info["local"])
        self.assertTrue(info["suggested"])

    def test_an_unknown_provider_returns_nothing(self):
        self.assertEqual({}, provider_info("does_not_exist"))

    def test_a_custom_endpoint_never_receives_the_key_when_marked_local(self):
        runtime, hass = make_runtime()
        runtime.ai["endpoint"] = "http://localhost:11434/v1"
        runtime.prepare_ai_preview()
        provider = build_transport(runtime, hass, provider_id="local_model")

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        run(provider.complete(runtime._ai_preview))
        self.assertNotIn("Authorization", hass.http_session.requests[0]["headers"])


if __name__ == "__main__":
    unittest.main()
