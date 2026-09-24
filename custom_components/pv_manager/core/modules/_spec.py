"""Datenmodell für Store-Karten (Addons).

Eine :class:`ModuleSpec` beschreibt genau eine Karte im internen Store. Die
Datenklassen sind bewusst rein: kein Home-Assistant-Import, keine Logik.

Felder im Überblick
-------------------

``module_id``
    Stabile, eindeutige Kennung (kleingeschrieben, Unterstriche). Wird im
    Speicher, in Tests und in der Oberfläche referenziert und darf sich nach
    der ersten Veröffentlichung nicht mehr ändern.
``name_de`` / ``name_en``
    Anzeigename der Karte in beiden Sprachen.
``summary_de`` / ``summary_en``
    Kurze, einfache Beschreibung für die Store-Karte.
``category``
    Kategorie im Store; bestimmt zugleich den Ordner der Addon-Datei
    (siehe ``_registry.py``).
``icon``
    Material-Design-Icon (``mdi:...``) für die Karte.
``optional``
    ``False`` nur für das Kernsystem: kann nicht ausgeschaltet werden.
``default_enabled``
    Aktiv bei frischer Installation. Nur der Kern ist ``True``.
``safety_level``
    ``standard``, ``high`` oder ``mandatory``. Steuert die Hervorhebung und
    die Prüftiefe im Sicherheitsterminal.
``requires``
    Addons, die zusammen mit diesem aktiviert werden müssen (mindestens
    ``core``). Der Store löst die Kette automatisch auf.
``provides``
    Fähigkeiten, die dieses Addon dem Restsystem meldet. Ehrlich halten:
    nur aufführen, was wirklich geliefert wird.
``reason_de`` / ``reason_en``
    Ein Satz "Warum es sich lohnt" für die Karte.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModuleCategory(StrEnum):
    """Store-Kategorien; jeder Kategorie entspricht ein Ordner."""

    BASE = "base"
    ENERGY = "energy"
    DEVICES = "devices"
    INTELLIGENCE = "intelligence"
    SAFETY = "safety"
    COMFORT = "comfort"


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """Eine Karte im internen Store (ein Addon)."""

    module_id: str
    name_de: str
    name_en: str
    summary_de: str
    summary_en: str
    category: ModuleCategory
    icon: str
    optional: bool = True
    default_enabled: bool = False
    safety_level: str = "standard"
    requires: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    reason_de: str = ""
    reason_en: str = ""

    def as_dict(self, *, enabled: bool) -> dict[str, object]:
        """Return a serializable store card."""
        return {
            "module_id": self.module_id,
            "name_de": self.name_de,
            "name_en": self.name_en,
            "summary_de": self.summary_de,
            "summary_en": self.summary_en,
            "category": self.category.value,
            "icon": self.icon,
            "optional": self.optional,
            "enabled": enabled,
            "default_enabled": self.default_enabled,
            "safety_level": self.safety_level,
            "requires": list(self.requires),
            "provides": list(self.provides),
            "reason_de": self.reason_de,
            "reason_en": self.reason_en,
        }
