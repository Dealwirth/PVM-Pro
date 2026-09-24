"""Contract tests between parts that cannot import each other.

The panel and the WebSocket API only agree on command names *as strings*, and
the Home Assistant service schemas live in YAML while the registration lives in
Python. Nothing type-checks those links, and a typo would only show up as a
dead button in a running Home Assistant. They are asserted here instead.

These tests need neither Home Assistant nor voluptuous, so they stay fast.
"""

from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

from custom_components.pv_manager import const

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "pv_manager"
FRONTEND = INTEGRATION / "frontend"

# Commands the panel actually calls. Extraction is regex based, so this list
# guards against the extraction silently finding nothing.
MUST_BE_CALLED_BY_THE_PANEL = {
    "get_state",
    "control_device",
    "emergency_stop",
    "register_device",
    "update_settings",
}

MUST_BE_REGISTERED_BY_THE_API = {
    "get_state",
    "control_device",
    "emergency_stop",
    "register_device",
    "set_module",
    "request_ai",
}


def frontend_commands() -> set[str]:
    """Return every ``pv_manager/...`` command the frontend sends."""
    found: set[str] = set()
    for path in sorted(FRONTEND.glob("*.js")):
        if path.name == "i18n.js":
            continue
        found.update(re.findall(r"pv_manager/([a-z_]+)", path.read_text(encoding="utf-8")))
    return found


def websocket_commands() -> set[str]:
    """Return every command name the WebSocket API registers."""
    text = (INTEGRATION / "websocket_api.py").read_text(encoding="utf-8")
    return set(re.findall(r'f"\{DOMAIN\}/([a-z_]+)"', text))


def documented_service_names() -> set[str]:
    """Return the top-level service names declared in ``services.yaml``."""
    text = (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
    return {line[: -len(":")] for line in text.splitlines() if re.fullmatch(r"[a-z_]+:", line)}


def declared_service_constants() -> set[str]:
    """Return the service names the integration declares as constants."""
    return {
        value for name, value in vars(const).items() if name.startswith("SERVICE_") and isinstance(value, str)
    }


class PanelToApiContractTest(unittest.TestCase):
    """Every command the panel sends must exist in the API."""

    def test_the_panel_calls_the_commands_we_expect(self):
        self.assertTrue(MUST_BE_CALLED_BY_THE_PANEL.issubset(frontend_commands()))

    def test_the_api_registers_the_commands_we_expect(self):
        self.assertTrue(MUST_BE_REGISTERED_BY_THE_API.issubset(websocket_commands()))

    def test_no_panel_command_is_missing_from_the_api(self):
        missing = frontend_commands() - websocket_commands()
        self.assertEqual(set(), missing, f"panel calls unknown commands: {sorted(missing)}")

    def test_control_commands_are_exposed_to_the_panel(self):
        # The two actions with real world consequences must be reachable.
        self.assertIn("control_device", frontend_commands())
        self.assertIn("emergency_stop", frontend_commands())


class ServiceSchemaContractTest(unittest.TestCase):
    """Documented services and registered services must be the same set."""

    def test_every_declared_service_is_documented(self):
        documented = documented_service_names()
        self.assertEqual(set(), declared_service_constants() - documented)

    def test_every_documented_service_is_actually_declared(self):
        documented = documented_service_names()
        self.assertEqual(set(), documented - declared_service_constants())

    def test_documented_services_have_a_user_facing_name(self):
        """A service without a name shows up as a bare key in the UI."""
        text = (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
        blocks: dict[str, list[str]] = {}
        current: str | None = None
        for line in text.splitlines():
            if re.fullmatch(r"[a-z_]+:", line):
                current = line[:-1]
                blocks[current] = []
            elif current is not None:
                blocks[current].append(line)
        self.assertTrue(blocks)
        for name, lines in blocks.items():
            self.assertTrue(
                any(re.match(r"\s+name:", line) for line in lines),
                f"service {name} has no name",
            )

    def test_services_never_claim_a_response_schema(self):
        """``services.yaml`` must not contain ``response:`` blocks."""
        text = (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
        self.assertNotIn("response:", text)


class VersionConsistencyTest(unittest.TestCase):
    """Version numbers drift silently, so they are compared here."""

    def manifest(self) -> dict:
        return json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    def test_all_version_statements_agree(self):
        manifest = self.manifest()
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(const.VERSION, manifest["version"])
        self.assertEqual(const.VERSION, package["version"])
        self.assertEqual(const.VERSION, project["project"]["version"])

    def test_manifest_declares_the_domain_the_panel_uses(self):
        manifest = self.manifest()
        self.assertEqual(const.DOMAIN, manifest["domain"])
        self.assertEqual("pv_manager", manifest["domain"])
        # The panel is registered as a custom sidebar entry, never as a card.
        self.assertIn("panel_custom", manifest["dependencies"])

    def test_manifest_urls_point_at_the_same_repository(self):
        manifest = self.manifest()
        documentation = manifest["documentation"]
        issue_tracker = manifest["issue_tracker"]
        self.assertTrue(documentation.startswith("https://"))
        self.assertEqual(f"{documentation}/issues", issue_tracker)

    def test_hacs_json_agrees_with_the_readme_minimum(self):
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        minimum = hacs["homeassistant"]
        self.assertRegex(minimum, r"^\d{4}\.\d+\.\d+$")
        # The README names the release line ("2025.6"), the manifest the full
        # version, so compare the part both are talking about.
        release_line = ".".join(minimum.split(".")[:2])
        self.assertIn(
            release_line,
            readme,
            f"README does not state the required Home Assistant version {release_line}",
        )

    def test_brand_assets_exist_where_hacs_looks_for_them(self):
        self.assertTrue((ROOT / "brand" / "icon.png").is_file())
        self.assertTrue((INTEGRATION / "brand" / "icon.png").is_file())


if __name__ == "__main__":
    unittest.main()
