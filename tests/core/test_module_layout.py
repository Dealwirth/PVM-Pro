"""Strukturtests für den Addon-Ordner (core/modules).

Ein Addon = eine Datei unter ``core/modules/<kategorie>/<module_id>.py``.
Diese Tests halten die Anatomie fest, damit die Ordnerstruktur für
Entwickler verlässlich bleibt (siehe docs/ADDONS.md).
"""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

from custom_components.pv_manager.core.modules import (
    MODULE_SPECS,
    MODULES_BY_ID,
    ModuleCategory,
    ModuleSpec,
)

MODULES_DIR = Path(__file__).resolve().parents[2] / "custom_components" / "pv_manager" / "core" / "modules"


class ModuleLayoutTest(unittest.TestCase):
    """Anatomy of the addon folder."""

    def test_every_category_has_a_folder(self) -> None:
        for category in ModuleCategory:
            self.assertTrue(
                (MODULES_DIR / category.value).is_dir(),
                f"category folder missing: {category.value}",
            )

    def test_every_spec_file_lives_in_its_category_folder(self) -> None:
        for module_id, spec in MODULES_BY_ID.items():
            expected = MODULES_DIR / spec.category.value / f"{module_id}.py"
            self.assertTrue(
                expected.is_file(),
                f"addon file missing or misplaced: {expected}",
            )

    def test_every_addon_file_exports_matching_spec(self) -> None:
        for category in ModuleCategory:
            folder = MODULES_DIR / category.value
            for addon_file in sorted(folder.glob("*.py")):
                if addon_file.name == "__init__.py":
                    continue
                dotted = f"custom_components.pv_manager.core.modules.{category.value}.{addon_file.stem}"
                module = importlib.import_module(dotted)
                spec = getattr(module, "SPEC", None)
                self.assertIsInstance(
                    spec,
                    ModuleSpec,
                    f"{dotted} exports no SPEC",
                )
                self.assertEqual(
                    spec.module_id,
                    addon_file.stem,
                    f"module_id must match filename: {dotted}",
                )

    def test_every_addon_file_is_self_explaining(self) -> None:
        """Jede Addon-Datei erklärt sich selbst: Docstring mit Ort und Bezug."""
        for module_id, spec in MODULES_BY_ID.items():
            path = MODULES_DIR / spec.category.value / f"{module_id}.py"
            docstring = path.read_text(encoding="utf-8").split('"""', 2)[1]
            self.assertIn("Addon:", docstring, f"{path} docstring names the addon")
            self.assertIn("Ort im Store", docstring, f"{path} docstring names its place")
            self.assertIn("Hängt an", docstring, f"{path} docstring names dependencies")

    def test_public_api_from_package_init(self) -> None:
        """Die stabile Schnittstelle hängt am Paket, nicht an Unterdateien."""
        package = importlib.import_module("custom_components.pv_manager.core.modules")
        for name in (
            "CORE_MODULE",
            "CORE_MODULE_ID",
            "MODULES_BY_ID",
            "MODULE_SPECS",
            "ModuleCategory",
            "ModuleSpec",
            "default_enabled_modules",
            "dependents_of",
            "resolve_dependencies",
            "store_cards",
        ):
            self.assertTrue(hasattr(package, name), f"public API member missing: {name}")

    def test_store_order_starts_with_core_and_groups_categories(self) -> None:
        self.assertEqual(MODULE_SPECS[0].module_id, "core")
        self.assertEqual(MODULE_SPECS[0].category, ModuleCategory.BASE)
        tail_categories = [spec.category for spec in MODULE_SPECS[1:]]
        self.assertNotIn(ModuleCategory.BASE, tail_categories)


if __name__ == "__main__":
    unittest.main()
